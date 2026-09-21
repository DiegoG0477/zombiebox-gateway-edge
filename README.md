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

Dev.13: Pins the same retry/live-TS implementation; no native lifecycle or Bionic evidence added.

## dev.14 increment

Pins the shared HLS/DASH adapter; native FFmpeg and Termux/Bionic execution remain unverified.
The four requested block-1 changes are implemented; physical acceptance and broader product gates remain open.

Dev.16: Pins shared core; native service lifecycle, boot/wake/doctor/update/uninstall and an explicitly experimental UxPlay source installer. Bionic execution remains unverified.

```sh
bash edge.sh doctor
bash edge.sh start zombied zombie-mediamtx
bash edge.sh boot-enable zombied zombie-mediamtx  # requires Termux:Boot opened once
bash edge.sh status
bash edge.sh stop
bash edge.sh update --with-probes --with-cast --with-youtube
bash edge.sh boot-disable
bash edge.sh uninstall  # removes services; preserves private data/media/config
```

`install-airplay-experimental.sh` is an opt-in native source build experiment.
It checks native OpenSSL/libplist/GStreamer development libraries and RTP plugins,
builds the locked UxPlay source without editing the reference clone, and installs
`zombie-airplay` stopped with private PIN/configuration. No Termux compile, mDNS,
A/V negotiation, reboot or thermal acceptance has yet been recorded. Rebrowser
remains a remote Full feature. Disabling the owned wake lock releases Termux's
process-level wake lock; coordinate that with other Termux workloads.

## License

First-party code: [GPL-3.0-only](LICENSE). See [NOTICE](NOTICE) for third-party scope.

Dev.18 retains processed artwork across restarts in `artwork` beside the configured SQLite state file.
The shared cache defaults to 64 MiB/24 hours; `-artwork-cache-mb 0` disables disk
persistence. Source URLs/credentials/original images are not stored in cache files.

Dev.19: Pins the same dev.19 core with no Linux/Android code fork; native Bionic validation remains pending.

Dev.20: Pins shared dev.20 core and adds bounded version/resource/installation diagnostics without reading private service configuration.

`edge.sh doctor` now includes a JSON resource/tool/installation report. The
standalone `scripts/doctor.py` is Termux-only at its CLI boundary; host fixtures
exercise report generation without pretending to run Android. Tool presence does
not imply module/account readiness, and the report never reads service run files,
provider configuration or tokens.
