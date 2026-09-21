#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
if [[ ${PREFIX:-} != /data/data/com.termux/files/usr ]]; then
    echo 'Run this script inside Termux on Android, not on Fedora.' >&2
    exit 1
fi
repo=$(cd "$(dirname "$0")/.." && pwd)
with_cast=false
with_youtube=false
with_probes=false
for argument in "$@"; do
    case "$argument" in --with-probes) with_probes=true ;; --with-cast) with_cast=true ;; --with-youtube) with_youtube=true ;; *)
        echo "Unknown option: $argument" >&2
        exit 1
        ;;
    esac
done
for program in go clang sv ffmpeg ffprobe; do
    command -v "$program" >/dev/null || {
        echo 'Install: pkg install golang clang termux-services ffmpeg' >&2
        exit 1
    }
done
if $with_cast; then
    upstream="$repo/third_party/sources/mediamtx"
    [[ $(git -C "$upstream" rev-parse HEAD) == 048255986f7e04b859b4c4efe651448ec785ecd4 ]] || {
        echo 'Restore pinned sources with make references first.' >&2
        exit 1
    }
    command -v tar >/dev/null
fi
if $with_youtube; then
    command -v node >/dev/null && command -v npm >/dev/null || {
        echo 'Install a native Node >=22 runtime and npm.' >&2
        exit 1
    }
fi
umask 077
runtime="$HOME/.zombie"
mkdir -p "$runtime"/{media,bin,config,state,cache,logs,probes}
if $with_probes; then
    command -v python3 >/dev/null || {
        echo "Install Python: pkg install python" >&2
        exit 1
    }
    python3 "$repo/scripts/generate-probes.py" --output "$runtime/probes"
fi
chmod 700 "$runtime" "$runtime/config" "$runtime/state"
(cd "$repo/gateway" && CGO_ENABLED=1 GOTOOLCHAIN=local GOMAXPROCS=2 go build -p 2 -trimpath -o "$runtime/bin/zombied" ./cmd/zombied)
[[ -f "$runtime/config/providers.json" ]] || printf '{}\n' >"$runtime/config/providers.json"
if [[ ! -f "$runtime/config/runtime.env" ]]; then
    token=$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')
    printf 'ZOMBIE_RELAY_ADMIN_TOKEN=%s\nZOMBIE_LISTEN=127.0.0.1:8090\nZOMBIE_RTSP_LISTEN=127.0.0.1:8554\n' "$token" >"$runtime/config/runtime.env"
fi
if $with_cast; then
    # Build in a disposable copy; never generate files or apply changes inside the reference clone.
    build=$(mktemp -d "$runtime/cache/mediamtx.XXXXXX")
    trap 'rm -rf "$build"' EXIT
    git -C "$upstream" archive HEAD | tar -x -C "$build"
    (cd "$build" && git apply "$repo/wrappers/mediamtx/android.patch")
    printf 'v1.21.1\n' >"$build/internal/core/VERSION"
    # The gateway serves semantic screens; the upstream standalone HLS web player is unused.
    printf '/* Standalone HLS web player omitted from the Edge package. */\n' >"$build/internal/servers/hls/hls.min.js"
    (cd "$build" && CGO_ENABLED=0 GOTOOLCHAIN=local GOMAXPROCS=2 go build -p 2 -trimpath -ldflags='-s -w -checklinkname=0' -o "$runtime/bin/mediamtx" .)
    cp "$repo/wrappers/mediamtx/mediamtx.yml" "$runtime/config/mediamtx.yml"
    service="$PREFIX/var/service/zombie-mediamtx"
    mkdir -p "$service"
    touch "$service/down"
    cat >"$service/run" <<'RUN'
#!/data/data/com.termux/files/usr/bin/sh
exec 2>&1
set -a
. "$HOME/.zombie/config/runtime.env"
set +a
export GOMEMLIMIT=96MiB GOMAXPROCS=1
export MTX_AUTHHTTPADDRESS="http://127.0.0.1:8090/internal/relay/auth?key=$ZOMBIE_RELAY_ADMIN_TOKEN"
export MTX_RTSPADDRESS="$ZOMBIE_RTSP_LISTEN" MTX_HLSADDRESS=127.0.0.1:8888 MTX_APIADDRESS=127.0.0.1:9997
exec "$HOME/.zombie/bin/mediamtx" "$HOME/.zombie/config/mediamtx.yml"
RUN
    chmod +x "$service/run"
    touch "$runtime/config/cast.enabled"
fi
if $with_youtube; then
    mkdir -p "$runtime/youtube"
    cp "$repo/wrappers/youtube/"{package.json,package-lock.json,server.mjs,worker.mjs,interpreter.mjs} "$runtime/youtube/"
    (cd "$runtime/youtube" && npm ci --ignore-scripts --no-audit --no-fund)
    if [[ ! -f "$runtime/config/youtube.json" ]]; then
        node -e 'const fs=require("node:fs"),crypto=require("node:crypto");fs.writeFileSync(process.argv[1],JSON.stringify({token:crypto.randomBytes(32).toString("hex"),cookie:"",visitorData:"",poToken:""})+"\n",{mode:0o600,flag:"wx"})' "$runtime/config/youtube.json"
    fi
    node - "$runtime/config/providers.json" "$runtime/config/youtube.json" <<'NODE'
const fs=require('node:fs');const file=process.argv[2],worker=JSON.parse(fs.readFileSync(process.argv[3]));const providers=JSON.parse(fs.readFileSync(file));
if(!providers.youtube){providers.youtube={enabled:false,url:'http://127.0.0.1:8091',token:worker.token,catalogId:''};fs.writeFileSync(file+'.tmp',JSON.stringify(providers,null,2)+'\n',{mode:0o600});fs.renameSync(file+'.tmp',file);}
NODE
    service="$PREFIX/var/service/zombie-youtube"
    mkdir -p "$service"
    touch "$service/down"
    cat >"$service/run" <<'RUN'
#!/data/data/com.termux/files/usr/bin/sh
exec 2>&1
export ZOMBIE_YOUTUBE_CONFIG="$HOME/.zombie/config/youtube.json"
export NODE_OPTIONS=--max-old-space-size=128
exec node "$HOME/.zombie/youtube/server.mjs"
RUN
    chmod +x "$service/run"
fi
service="$PREFIX/var/service/zombied"
mkdir -p "$service"
touch "$service/down"
cat >"$service/run" <<'RUN'
#!/data/data/com.termux/files/usr/bin/sh
exec 2>&1
set -a
. "$HOME/.zombie/config/runtime.env"
set +a
export GOMEMLIMIT=192MiB GOMAXPROCS=2
set -- -probe-dir "$HOME/.zombie/probes" -listen "$ZOMBIE_LISTEN" -state "$HOME/.zombie/state/gateway.db" -media-dir "$HOME/.zombie/media" -config "$HOME/.zombie/config/providers.json" -media-tools
if [ -f "$HOME/.zombie/config/cast.enabled" ]; then
  set -- "$@" -relay-url http://127.0.0.1:8888 -relay-control-url http://127.0.0.1:9997
fi
exec "$HOME/.zombie/bin/zombied" "$@"
RUN
chmod +x "$service/run"
{
    go version
    ffmpeg -version | sed -n '1p'
    ffprobe -version | sed -n '1p'
} >"$runtime/build-info.txt"
if $with_cast; then printf 'MediaMTX 1.21.1 + android.patch; anet requires checklinkname=0\n' >>"$runtime/build-info.txt"; fi
if $with_youtube; then node --version >>"$runtime/build-info.txt"; fi
printf 'Installed stopped native services. Enable zombied and selected zombie-mediamtx/zombie-youtube with sv-enable.\n'
printf 'Review %s/config/runtime.env for LAN addresses; credentials and existing providers were preserved.\n' "$runtime"
