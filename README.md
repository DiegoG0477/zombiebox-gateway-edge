# Gateway Edge

Uses the same `../gateway/` core inside Termux; Android 7+ is the target. No Docker and no assumption that linux/arm64 binaries run on Android.

Inside Termux:

```sh
pkg install git golang termux-services
# Clone this monorepo once a remote exists, then enter it.
bash gateway-edge/install-termux.sh
# Restart the shell if required by termux-services.
sv-enable zombied
```

The installer builds with installed native Go (`GOTOOLCHAIN=local` prevents an incompatible Linux toolchain download). Go >=1.25 is required; verify package availability for the actual Android version. It creates a stopped service with loopback binding. Adjust its run file for an explicit LAN address when needed; measure thermal/battery behavior. Termux:Boot and wake locks are not configured automatically.

Fedora does not validate this runtime. Local Rebrowser is unsupported in Edge V1. FFmpeg/MediaMTX and other workers follow after Bionic package/binary validation.
