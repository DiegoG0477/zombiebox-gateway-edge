#!/data/data/com.termux/files/usr/bin/bash
# Explicit native build experiment. Successful compilation is not receiver validation.
set -euo pipefail
[[ ${PREFIX:-} == /data/data/com.termux/files/usr ]] || {
    echo 'Run inside Termux on Android.' >&2
    exit 1
}
component=$(cd "$(dirname "$0")" && pwd)
repo=$(python3 "$component/scripts/dependencies.py" check gateway-core)
runtime="$HOME/.zombie"
[[ -x "$runtime/bin/zombied" ]] || {
    echo 'Install the Edge gateway first.' >&2
    exit 1
}
for tool in cmake make clang clang++ pkg-config git tar go python3 ffmpeg gst-inspect-1.0; do command -v "$tool" >/dev/null; done
pkg-config --exists openssl libplist-2.0 gstreamer-1.0 gstreamer-video-1.0 gstreamer-audio-1.0
for element in rtpL16pay rtph264pay multiudpsink udpsink; do gst-inspect-1.0 "$element" >/dev/null; done
upstream="$repo/third_party/sources/uxplay"
commit=57ea83411d5f7e0b38c5841987439340543f025c
[[ $(git -C "$upstream" rev-parse HEAD) == "$commit" ]] || {
    echo 'Restore locked UxPlay sources first.' >&2
    exit 1
}
umask 077
build=$(mktemp -d "$runtime/cache/uxplay.XXXXXX")
trap 'rm -rf "$build"' EXIT
git -C "$upstream" archive HEAD | tar -x -C "$build"
cmake -S "$build" -B "$build/build" -DNO_X11_DEPS=ON -DUSE_MDNS=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$build/build" -j2
cp "$build/build/uxplay" "$runtime/bin/uxplay"
(cd "$repo/gateway" && CGO_ENABLED=0 GOTOOLCHAIN=local GOMAXPROCS=2 go build -p 2 -trimpath -o "$runtime/bin/zombie-worker" ./cmd/zombie-worker)
mkdir -p "$runtime/licenses/uxplay" "$runtime/airplay"
cp "$build/LICENSE" "$runtime/licenses/uxplay/LICENSE"
printf '%s\n' "$commit" >"$runtime/licenses/uxplay/COMMIT"
python3 - "$runtime" <<'PY'
import json
import pathlib
import secrets
import sys

root = pathlib.Path(sys.argv[1])
worker = root / 'config/airplay-worker.json'
if not worker.exists():
    worker.write_text(json.dumps(dict(mode='airplay', listen='127.0.0.1:8093', token=secrets.token_hex(32), pin=f'{secrets.randbelow(10000):04}', stateDir=str(root / 'airplay'))) + '\n')
provider_file = root / 'config/providers.json'
providers = json.loads(provider_file.read_text())
if 'airplay' not in providers:
    providers['airplay'] = dict(enabled=False, url='http://127.0.0.1:8093', token=json.loads(worker.read_text())['token'])
    temp = provider_file.with_suffix('.tmp')
    temp.write_text(json.dumps(providers, indent=2) + '\n')
    temp.replace(provider_file)
PY
service="$PREFIX/var/service/zombie-airplay"
mkdir -p "$service"
touch "$service/down"
cat >"$service/run" <<'RUN'
#!/data/data/com.termux/files/usr/bin/sh
export PATH="$HOME/.zombie/bin:$PATH" GOMEMLIMIT=128MiB GOMAXPROCS=1
export GST_REGISTRY="$HOME/.zombie/airplay/gstreamer-registry.bin"
exec zombie-worker -config "$HOME/.zombie/config/airplay-worker.json"
RUN
chmod +x "$service/run"
echo 'Experimental native AirPlay build installed stopped. Validate mDNS, PIN, A/V and thermals on the Android host before enabling it.'
