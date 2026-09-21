#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
runtime="$HOME/.zombie"
set -a
source "$runtime/config/runtime.env"
set +a
export GOMEMLIMIT=192MiB GOMAXPROCS=2
listen=${ZOMBIE_LISTEN:-0.0.0.0:8090}
args=(-listen "$listen" -state "$runtime/state/gateway.db" -media-dir "$runtime/media" -config "$runtime/config/providers.json" -media-tools -probe-dir "$runtime/current/probes")
if [[ $listen != 127.0.0.1:* && $listen != localhost:* && $listen != '[::1]:'* ]]; then
    args+=(-discovery-listen "${ZOMBIE_DISCOVERY_BIND:-0.0.0.0:8098}" -discovery-http-port "${listen##*:}")
fi
if [[ -f $runtime/config/cast.enabled ]]; then
    args+=(-relay-url http://127.0.0.1:8888 -relay-control-url http://127.0.0.1:9997)
fi
exec "$runtime/current/bin/zombied" "${args[@]}"
