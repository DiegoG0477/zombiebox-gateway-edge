#!/data/data/com.termux/files/usr/bin/bash
# Native service lifecycle. Runtime credentials are never printed.
set -euo pipefail
if [[ ${PREFIX:-} != /data/data/com.termux/files/usr ]]; then
    echo 'Run inside Termux on Android.' >&2
    exit 1
fi
component=$(cd "$(dirname "$0")" && pwd)
runtime="$HOME/.zombie"
services=(zombied zombie-mediamtx zombie-youtube zombie-youtube-receiver zombie-spotify zombie-threadfin zombie-airplay)
service_name() {
    local candidate=$1 allowed
    for allowed in "${services[@]}"; do
        if [[ $candidate == "$allowed" && -x "$PREFIX/var/service/$allowed/run" ]]; then
            printf '%s\n' "$PREFIX/var/service/$allowed"
            return
        fi
    done
    echo "Unsupported or uninstalled service: $candidate" >&2
    return 1
}
stop_all() {
    local name path
    for name in "${services[@]}"; do
        path="$PREFIX/var/service/$name"
        if [[ -d $path ]]; then
            touch "$path/down"
            sv -w 10 down "$path" || true
        fi
    done
    if [[ -f "$runtime/state/wake-owned" ]]; then
        termux-wake-unlock
        rm "$runtime/state/wake-owned"
    fi
}
case ${1:-status} in
    start)
        shift
        [[ $# -gt 0 ]] || set -- zombied
        command -v termux-wake-lock >/dev/null
        mkdir -p "$runtime/state"
        # Validate the full selection before changing any service state.
        for name in "$@"; do service_name "$name" >/dev/null; done
        termux-wake-lock
        touch "$runtime/state/wake-owned"
        for name in "$@"; do
            path=$(service_name "$name")
            rm -f "$path/down"
            sv -w 10 up "$path"
        done
        ;;
    stop) stop_all ;;
    status)
        for name in "${services[@]}"; do
            path="$PREFIX/var/service/$name"
            if [[ -d $path ]]; then sv status "$path" || true; fi
        done
        ;;
    doctor)
        python3 "$component/scripts/doctor.py" "${@:2}"
        failed=0
        programs=(sv ffmpeg ffprobe termux-wake-lock termux-wake-unlock)
        [[ -f $component/release.json ]] || programs+=(go clang)
        for program in "${programs[@]}"; do
            if command -v "$program" >/dev/null; then printf 'Available: %s\n' "$program"; else
                printf 'Missing: %s\n' "$program"
                failed=1
            fi
        done
        printf 'Android API: %s\n' "$(getprop ro.build.version.sdk)"
        printf 'Architecture: %s\n' "$(uname -m)"
        df -h "$runtime"
        [[ -r "$runtime/build-info.txt" ]] && cat "$runtime/build-info.txt"
        [[ -x "$runtime/bin/zombied" ]] || {
            echo 'Gateway is not installed.'
            failed=1
        }
        printf 'AirPlay/UxPlay: experimental, not installed by the supported module installer.\nBrowser: remote Full only.\n'
        exit "$failed"
        ;;
    boot-enable)
        shift
        [[ $# -gt 0 ]] || set -- zombied
        for name in "$@"; do service_name "$name" >/dev/null; done
        mkdir -p "$HOME/.termux/boot"
        umask 077
        {
            printf '#!/data/data/com.termux/files/usr/bin/bash\n'
            printf 'source "$PREFIX/etc/profile.d/start-services.sh"\n'
            printf 'exec bash %q start' "$component/edge.sh"
            printf ' %q' "$@"
            printf '\n'
        } >"$HOME/.termux/boot/zombiebox"
        chmod 700 "$HOME/.termux/boot/zombiebox"
        echo 'Boot hook installed. Install and open Termux:Boot once; permit background operation in Android settings.'
        ;;
    boot-disable) rm -f "$HOME/.termux/boot/zombiebox" ;;
    module)
        shift
        case " $* " in
            *' --module youtube '* | *' --module youtube-receiver '*)
                exec python3 "$component/scripts/install-node-module.py" "$@"
                ;;
        esac
        exec python3 "$component/scripts/install-module.py" "$@"
        ;;
    update)
        shift
        if [[ -f $component/release.json ]]; then
            # The binary installer validates the replacement before stopping core.
            exec bash "$component/install.sh" "$@"
        fi
        # Installer verifies the exact clean core pin before stopping runtime.
        python3 "$component/scripts/dependencies.py" check gateway-core >/dev/null
        stop_all
        bash "$component/install-termux.sh" "$@"
        echo 'Updated services remain stopped. Start the configured modules explicitly.'
        ;;
    uninstall)
        stop_all
        rm -f "$HOME/.termux/boot/zombiebox"
        for name in "${services[@]}"; do
            path="$PREFIX/var/service/$name"
            if [[ -d $path ]]; then
                sv exit "$path" || true
                rm -rf -- "$path"
            fi
        done
        echo 'Service definitions removed. Private runtime, credentials, media and backups remain in ~/.zombie.'
        ;;
    *)
        echo 'Usage: edge.sh start [services...] | stop | status | doctor | boot-enable [services...] | boot-disable | update [installer flags...] | module [installer flags...] | uninstall' >&2
        exit 2
        ;;
esac
