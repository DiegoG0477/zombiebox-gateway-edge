#!/data/data/com.termux/files/usr/bin/bash
# Native optional packages; the shared gateway remains the only application core.
set -euo pipefail
[[ ${PREFIX:-} == /data/data/com.termux/files/usr ]] || {
    echo 'Run inside Termux on Android.' >&2
    exit 1
}
repo=$(cd "$(dirname "$0")/.." && pwd)
runtime="$HOME/.zombie"
[[ -x "$runtime/bin/zombied" ]] || {
    echo 'Run install-termux.sh first.' >&2
    exit 1
}
[[ $# -gt 0 ]] || {
    echo 'Usage: install-services.sh spotify|threadfin [...]' >&2
    exit 1
}
for tool in go clang python3 git tar; do command -v "$tool" >/dev/null; done
umask 077
for name in "$@"; do
    case "$name" in
        spotify)
            source_name=go-librespot
            commit=57d7278d94a9233060c2a6238f5926ffd1e72de4
            command -v pkg-config >/dev/null
            pkg-config --exists ogg vorbis flac libmpg123 || {
                echo 'Install native libogg, libvorbis, libflac, mpg123 and pkg-config development files.' >&2
                exit 1
            }
            ;;
        threadfin)
            source_name=threadfin
            commit=6b9c0ccf16164eb362af0a44660228267734c5aa
            ;;
        *)
            echo "Unsupported native package: $name" >&2
            exit 1
            ;;
    esac
    upstream="$repo/third_party/sources/$source_name"
    [[ $(git -C "$upstream" rev-parse HEAD) == "$commit" ]] || {
        echo 'Run make references first.' >&2
        exit 1
    }
    build=$(mktemp -d "$runtime/cache/$source_name.XXXXXX")
    trap 'rm -rf "$build"' EXIT
    git -C "$upstream" archive HEAD | tar -x -C "$build"
    if [[ $name == spotify ]]; then
        (cd "$build" && CGO_ENABLED=1 GOTOOLCHAIN=local GOMAXPROCS=2 go build -mod=readonly -p 2 -trimpath -o "$runtime/bin/go-librespot" ./cmd/daemon)
        (cd "$repo/gateway" && CGO_ENABLED=0 GOTOOLCHAIN=local GOMAXPROCS=2 go build -p 2 -trimpath -o "$runtime/bin/zombie-worker" ./cmd/zombie-worker)
    else
        (cd "$build" && CGO_ENABLED=0 GOTOOLCHAIN=local GOMAXPROCS=2 go build -mod=readonly -p 2 -trimpath -o "$runtime/bin/threadfin" .)
    fi
    mkdir -p "$runtime/licenses/$source_name" "$runtime/$name"
    cp "$build/LICENSE" "$runtime/licenses/$source_name/LICENSE"
    printf '%s\n' "$commit" >"$runtime/licenses/$source_name/COMMIT"
    rm -rf "$build"
    trap - EXIT
    if [[ $name == spotify ]]; then
        python3 - "$runtime" <<'PYTHON'
import json,pathlib,secrets,sys
root=pathlib.Path(sys.argv[1]);state=root/'spotify';worker=root/'config/spotify-worker.json'
if not worker.exists():
    worker.write_text(json.dumps(dict(mode='spotify',listen='127.0.0.1:8092',token=secrets.token_hex(32),stateDir=str(state)))+'\n')
config=state/'config.yml'
if not config.exists():
    config.write_text('device_name: Zombie Box Edge\ncredentials:\n  type: device_auth\nzeroconf_enabled: false\naudio_backend: pipe\naudio_output_pipe: '+str(state/'audio.pcm')+'\naudio_output_pipe_format: s16le\naudio_output_pipe_wait_for_reader: true\nvolume_steps: 100\nserver:\n  enabled: true\n  address: 127.0.0.1\n  port: 3678\n')
provider_file=root/'config/providers.json';providers=json.loads(provider_file.read_text())
if 'spotify' not in providers:
    providers['spotify']=dict(enabled=False,url='http://127.0.0.1:8092',token=json.loads(worker.read_text())['token'])
    temp=provider_file.with_suffix('.tmp');temp.write_text(json.dumps(providers,indent=2)+'\n');temp.replace(provider_file)
PYTHON
    fi
    service="$PREFIX/var/service/zombie-$name"
    mkdir -p "$service"
    touch "$service/down"
    if [[ $name == spotify ]]; then
        cat >"$service/run" <<'RUN'
#!/data/data/com.termux/files/usr/bin/sh
export PATH="$HOME/.zombie/bin:$PATH" GOMEMLIMIT=128MiB GOMAXPROCS=1
exec zombie-worker -config "$HOME/.zombie/config/spotify-worker.json"
RUN
    else
        cat >"$service/run" <<'RUN'
#!/data/data/com.termux/files/usr/bin/sh
export GOMEMLIMIT=128MiB GOMAXPROCS=1
exec "$HOME/.zombie/bin/threadfin" -config "$HOME/.zombie/threadfin" -bind 127.0.0.1 -port 34400
RUN
    fi
    chmod +x "$service/run"
    printf 'Installed stopped native service zombie-%s; physical runtime validation remains required.\n' "$name"
done
