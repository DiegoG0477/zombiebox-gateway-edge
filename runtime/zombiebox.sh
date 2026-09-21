#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
source "$PREFIX/etc/profile.d/start-services.sh"
exec bash "$HOME/.zombie/current/edge.sh" "${@:-start}"
