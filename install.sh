#!/usr/bin/env bash
# Download a pinned Android release. No Go, compiler, Docker or root on the phone.
set -euo pipefail
umask 077
if [[ ${PREFIX:-} != /data/data/com.termux/files/usr ]] || ! command -v getprop >/dev/null; then
    echo 'Run inside the standard Termux application on Android 7+.' >&2
    exit 1
fi
repository=''
version=''
bundle=''
checksum=''
while [[ $# -gt 0 ]]; do
    case $1 in
        --repository)
            repository=${2:?Missing repository}
            shift 2
            ;;
        --version)
            version=${2:?Missing version}
            shift 2
            ;;
        --bundle)
            bundle=${2:?Missing bundle}
            shift 2
            ;;
        --sha256)
            checksum=${2:?Missing checksum}
            shift 2
            ;;
        *)
            echo 'Usage: install.sh --repository OWNER/REPO [--version vX.Y.Z] | --bundle FILE --sha256 HASH' >&2
            exit 2
            ;;
    esac
done
if [[ -n $bundle ]]; then
    [[ -f $bundle && $checksum =~ ^[a-f0-9]{64}$ && -z $repository && -z $version ]] || {
        echo 'Local bundles require an explicit SHA256 and no remote options.' >&2
        exit 2
    }
else
    [[ $repository =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ && -z $checksum ]] || {
        echo 'Specify a published repository and no remote checksum override.' >&2
        exit 2
    }
fi
api=$(getprop ro.build.version.sdk)
[[ $api =~ ^[0-9]+$ && $api -ge 24 ]] || {
    echo 'Android API24+ is required for Edge.' >&2
    exit 1
}
# dpkg reports the installed Termux userland, unlike uname on a 64-bit kernel.
case $(dpkg --print-architecture) in
    aarch64) arch=arm64 ;;
    arm) arch=armv7 ;;
    *)
        echo 'Prebuilt Edge supports Termux aarch64 and arm userlands.' >&2
        exit 1
        ;;
esac
pkg install -y curl python ffmpeg termux-services
if [[ -z $bundle && -z $version ]]; then
    channel=${ZOMBIE_INSTALL_CHANNEL_URL:-https://raw.githubusercontent.com/$repository/main/install-channel.txt}
    version=$(curl --fail --location --silent --show-error --retry 3 --connect-timeout 10 --max-time 30 --max-filesize 128 "$channel") || {
        echo 'Could not resolve the current installable Edge release.' >&2
        exit 1
    }
fi
if [[ -z $bundle && ! $version =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][A-Za-z0-9.-]+)?$ ]]; then
    echo 'Invalid Edge release channel or version.' >&2
    exit 2
fi
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
if [[ -z $bundle ]]; then
    asset="zombiebox-gateway-android-$arch.tar.gz"
    base="https://github.com/$repository/releases/download/$version"
    curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 300 --max-filesize 134217728 "$base/$asset" -o "$temporary/$asset"
    curl --fail --show-error --silent --location --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 30 --max-filesize 1024 "$base/$asset.sha256" -o "$temporary/checksum"
    checksum=$(awk 'NR == 1 {print $1}' "$temporary/checksum")
    [[ $checksum =~ ^[a-f0-9]{64}$ ]] || {
        echo 'Malformed release checksum.' >&2
        exit 1
    }
    bundle="$temporary/$asset"
fi
printf '%s  %s\n' "$checksum" "$bundle" | sha256sum --check --status
# No extraction of links, devices, traversal paths or unbounded archives.
python3 - "$bundle" "$temporary/package" <<'PY'
import pathlib,sys,tarfile
destination=pathlib.Path(sys.argv[2]); destination.mkdir()
with tarfile.open(sys.argv[1], 'r:gz') as archive:
    members=[]; seen=set(); size=0
    for member in archive:
        size += member.size
        if len(members)>=256 or size>192*1024*1024:
            raise SystemExit('Release bundle exceeds its limits')
        members.append(member)
        path=pathlib.PurePosixPath(member.name)
        if not member.isfile() or path.is_absolute() or '..' in path.parts or path.as_posix()!=member.name or member.name in seen:
            raise SystemExit('Unsafe release member')
        seen.add(member.name)
    archive.extractall(destination, members=members, filter='data')
PY
python3 "$temporary/package/scripts/install-binary.py" "$temporary/package" "$arch" "$api" "${version:-local}" "$repository"
source "$PREFIX/etc/profile.d/start-services.sh"
bash "$HOME/.zombie/current/edge.sh" start
