# zombiebox-gateway-edge

Native Android/Termux deployment of the same Go core.

This is an independent repository in the Zombie Box workspace. Remotes and hosted
releases are not configured yet; local commits/tags and dependency pins are real.

Depends on the exact gateway-core commit in `dependencies.lock.json`.

```sh
make deps-check
make check      # shell syntax; can run on Fedora
# On the actual Android Termux host:
pkg install python git golang clang termux-services ffmpeg
bash install-termux.sh --with-probes --with-cast --with-youtube
bash install-services.sh spotify threadfin
bash install-youtube-receiver.sh
```

Optional modules require the native development libraries documented by their
core wrapper README. Restore core's locked references using `make -C ../gateway-core
references` before source builds. `ZOMBIE_CORE_DIR` selects a different checkout;
`make deps` restores `.deps/gateway-core` once a remote is configured. The installer
creates stopped runit services under Termux; enable only the modules you configure.

No Docker or downloaded Linux runtime binary is used. Core needs Go >=1.25;
pinned MediaMTX needs native Go >=1.26, and the receiver needs Node22.22.2+ within
22.x. Physical execution, boot/wake-lock work, UxPlay feasibility and thermal gates
remain open. Do not label a Fedora compile as Android/Bionic compatibility.

## Development rules

Run `make format` and `make format-check`. Formatters are pinned and downloaded
on first use. See [AGENTS.md](AGENTS.md), [history provenance](docs/history.md),
[component work](docs/PLANNING.md) and [local milestone registry](docs/milestones.json).
The central workspace owns product-wide ADRs, the original specification, the UI
reference, M0–M11 exit gates and the complete development/validation gap audit.
Physical devices over USB/ADB are the default; automated checks do not establish
legacy runtime or end-to-end account/media compatibility.

Dev.10 consumes the same local audio-track/text-subtitle core as Full. The installer
already enables `-media-tools`; its native Termux FFmpeg supplies the implementation.
Host tests do not establish Bionic decoder/subtitle compatibility. No parallel Go
implementation or Linux runtime binary is introduced.

Dev.11 consumes the same hierarchical browse, progressive remote adapter and
adaptive YouTube resolver as Full. Its native FFmpeg must support the restricted
HTTP/MP4/Matroska demuxers, H.264/AAC and fragmented MP4 output. The shared one-job
conversion bound remains in effect. Full container checks do not verify Termux.

Dev.12 pins the shared foreground media-receiver and Cast-budget core. No new
platform binary or native UxPlay support is implied. Native operation, boot/wake
lifecycle and the Android module support matrix remain separate work.
