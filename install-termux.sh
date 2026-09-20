#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
if [[ ${PREFIX:-} != /data/data/com.termux/files/usr ]]; then
  echo 'Run this script inside Termux on Android, not on Fedora.' >&2
  exit 1
fi
repo=$(cd "$(dirname "$0")/.." && pwd)
command -v go >/dev/null || { echo 'Install: pkg install golang clang termux-services'; exit 1; }
command -v clang >/dev/null || { echo 'Install: pkg install clang'; exit 1; }
command -v sv >/dev/null || { echo 'Install: pkg install termux-services'; exit 1; }
umask 077
mkdir -p "$HOME/.zombie/media" "$HOME/.zombie/bin" "$HOME/.zombie/config" "$HOME/.zombie/state" "$HOME/.zombie/cache" "$HOME/.zombie/logs"
cd "$repo/gateway"
CGO_ENABLED=1 GOTOOLCHAIN=local GOMAXPROCS=2 go build -p 2 -trimpath -o "$HOME/.zombie/bin/zombied" ./cmd/zombied
[[ -f "$HOME/.zombie/config/providers.json" ]] || printf '{}\n' > "$HOME/.zombie/config/providers.json"
service="$PREFIX/var/service/zombied"
mkdir -p "$service"
# Keep service stopped until the user explicitly enables it.
touch "$service/down"
cat > "$service/run" <<'RUN'
#!/data/data/com.termux/files/usr/bin/sh
exec 2>&1
export GOMEMLIMIT=192MiB GOMAXPROCS=2
exec "$HOME/.zombie/bin/zombied" -listen 127.0.0.1:8090 -state "$HOME/.zombie/state/gateway.db" -media-dir "$HOME/.zombie/media" -config "$HOME/.zombie/config/providers.json"
RUN
chmod +x "$service/run"
echo 'Installed. Restart Termux services shell if needed, then: sv-enable zombied'
