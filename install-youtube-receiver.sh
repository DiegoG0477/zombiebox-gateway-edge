#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
[[ ${PREFIX:-} == /data/data/com.termux/files/usr ]] || { echo 'Run inside Termux on Android.' >&2; exit 1; }
for tool in node npm python3; do command -v "$tool" >/dev/null; done
node -e 'const [major,minor,patch]=process.versions.node.split(".").map(Number);if(major!==22||minor<22||(minor===22&&patch<2)){process.stderr.write("This lock requires native Node 22.22.2 or a newer 22.x patch.\n");process.exit(1)}'
repo=$(cd "$(dirname "$0")/.." && pwd)
runtime="$HOME/.zombie"
[[ -x "$runtime/bin/zombied" ]] || { echo 'Install the shared gateway first.' >&2; exit 1; }
umask 077
mkdir -p "$runtime/youtube-receiver" "$runtime/config"
cp "$repo/wrappers/youtube-receiver/"{package.json,package-lock.json,server.mjs,bridge.mjs} "$runtime/youtube-receiver/"
(cd "$runtime/youtube-receiver" && npm ci --ignore-scripts --omit=dev --no-audit --no-fund)
python3 - "$runtime" <<'PY'
import json,pathlib,secrets,sys
root=pathlib.Path(sys.argv[1]);config=root/'config/youtube-receiver.json'
if not config.exists():config.write_text(json.dumps(dict(token=secrets.token_hex(32),listen='127.0.0.1',port=8095,dialPort=8096))+'\n')
path=root/'config/providers.json';providers=json.loads(path.read_text())
if 'youtube_receiver' not in providers:
    providers['youtube_receiver']=dict(enabled=False,url='http://127.0.0.1:8095',token=json.loads(config.read_text())['token'])
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(providers,indent=2)+'\n');temp.replace(path)
PY
service="$PREFIX/var/service/zombie-youtube-receiver"
mkdir -p "$service";touch "$service/down"
cat > "$service/run" <<'RUN'
#!/data/data/com.termux/files/usr/bin/sh
export ZOMBIE_YOUTUBE_RECEIVER_CONFIG="$HOME/.zombie/config/youtube-receiver.json"
cd "$HOME/.zombie/youtube-receiver"
exec node --max-old-space-size=192 server.mjs
RUN
chmod +x "$service/run"
printf 'Installed stopped native receiver. Enable its provider and runit service explicitly; a client must claim a lease before DIAL starts.\n'
