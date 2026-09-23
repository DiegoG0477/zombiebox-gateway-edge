# zombiebox-gateway-edge

Native Android/Termux deployment of the same Go core.

This is an independent repository in the Zombie Box workspace.
[Source and milestones](https://github.com/ZombieBox-tv/zombiebox-gateway-edge) are hosted on GitHub.
Development checkpoints are not stable releases or physical compatibility claims.

Depends on the exact gateway-core commit in `dependencies.lock.json`.

## Installation

### Prebuilt Android bundle (experimental dev.45)

Target: the standard Termux application on Android 7+/API24, with `aarch64` or `arm`
userland. ARMv7 and ARM64 are detected using `dpkg`, not the kernel's architecture.
No Docker, root, Go or C compiler is required by the binary installer. It installs
Termux's `curl`, `python`, `ffmpeg` and `termux-services` packages.

Download the version-pinned installer and review it, then install the core bundle:

```sh
bash install.sh --repository ZombieBox-tv/zombiebox-gateway-edge --version v0.1.0-dev.45
```

Equivalent one-line installation from the pinned release:

```sh
curl -fsSL https://raw.githubusercontent.com/ZombieBox-tv/zombiebox-gateway-edge/v0.1.0-dev.45/install.sh | bash -s -- --repository ZombieBox-tv/zombiebox-gateway-edge --version v0.1.0-dev.45
```

The [experimental release](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.45) pairs each ABI archive with its corresponding-source archive and checksums.
For a locally transferred build, supply its independently checked SHA256:

```sh
bash install.sh --bundle /path/zombiebox-gateway-android-arm64.tar.gz --sha256 SHA256_FROM_BUILD
```

The installer verifies the archive checksum, bounded safe extraction, individual
file hashes, ABI/API and Android PIE executable before stopping an existing core.
It preserves private configuration/SQLite/media, installs a versioned directory and
switches the launcher. Old directories remain available for operator recovery;
this is not an automatic database rollback. It starts the gateway with UDP8098 LAN
discovery. Dependencies and optional module installation remain visible; package
availability and actual Bionic behavior require Android validation.

```sh
zombiebox                 # start core; default after installation
zombiebox status
zombiebox doctor
zombiebox stop
zombiebox boot-enable     # optional Termux:Boot hook
zombiebox boot-disable
zombiebox update --repository ZombieBox-tv/zombiebox-gateway-edge --version v0.1.0-dev.45
zombiebox uninstall       # removes services, retains private data
```

Install **and open Termux:Boot once** for the optional boot hook. Exempt Termux from
battery optimization in Android settings. Startup acquires a wake lock; stopping
releases the lock owned by this installation. A wake lock cannot guarantee survival
against OEM process killing. Termux:Boot starts at boot, not whenever a charger is
connected. See [Termux:Boot's instructions](https://github.com/termux/termux-boot/blob/master/README.md).

This initial bundle contains core, SQLite and synthetic probes; FFmpeg comes from
Termux. The dev.37 [optional module path](docs/optional-modules.md) adds compiler-free
Threadfin packaging for both ABIs. Dev.38 adds the MediaMTX Android module builder/installer and resolves its inline
license inventory. YouTube catalog/TV receiver now have [public dev.45
modules](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.45)
with matching sources, checksums and a compiler-free stopped-service installer:

```sh
zombiebox module --module youtube --version v0.1.0-dev.45
zombiebox module --module youtube-receiver --version v0.1.0-dev.45
```

The installer obtains prebuilt Termux Node LTS when absent, validates its version,
and leaves each provider disabled until configured. Android execution remains an
acceptance gate. Spotify and experimental AirPlay retain native dependency closure
work. Modules are selected explicitly, never silently enabled.

### Available now: native source installation

The commands below are the existing developer path and require Go/Clang on the
phone. They do not establish Android runtime acceptance by themselves.

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
pinned MediaMTX needs native Go >=1.26. The receiver accepts Node22.22.2+ within
22.x or Node24.18.0+ within 24.x; the latter is a Termux prebuilt LTS candidate.
Physical execution, boot/wake-lock work, UxPlay feasibility and thermal gates
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

Dev.21: Pins shared dev.21 network/search/state maintenance without forking the core or claiming native runtime acceptance.

## dev.22 increment

Pins the same dev.22 receiver-coordination core; native Termux/Bionic execution remains unverified.
No product or physical acceptance gate closes.

## LAN discovery

New installations bind HTTP to `0.0.0.0:8090` on the trusted LAN and enable the
shared UDP8098 discovery responder. Existing `runtime.env` is preserved: loopback
HTTP bindings do not advertise onto the LAN. `ZOMBIE_DISCOVERY_BIND` optionally
overrides the UDP address; the advertised HTTP port follows `ZOMBIE_LISTEN`.
Android/Wi-Fi restrictions can still block broadcast. Manual pairing remains
available; discovery does not establish Bionic/OEM or physical acceptance.

## dev.23 increment

Shared native discovery for LAN bindings; existing private settings remain intact.
No product or physical acceptance gate closes.


## dev.24 increment

Consumes the same companion core and installs its QR encoder license. This adds no Linux binary, Docker requirement or native Android execution evidence.
Full visual/capture policy, extended Remote, HEVC/4K and other product gates remain open; physical acceptance stays deferred.

## dev.25 increment

Verified Android binary bootstrap, ABI/API checks, preserved config/SQLite, lifecycle launcher and NDK/cgo candidate build workflow. Actual Android cross-build/runtime and optional prebuilt modules remain pending.

## dev.26 increment

Android/Bionic PIE candidates have now cross-built for ARMv7 and ARM64 with
Go1.25.6, NDK28.2.13676358 and cgo SQLite. Both use Android's linker, depend only
on libc/libdl/liblog and resolve every required dynamic import against API24 NDK
stubs. ARM64 LOAD alignment is 16 KiB; ARMv7 is 4 KiB. These are host artifact
checks, not Bionic execution or physical acceptance. Optional modules and public
release assets remain pending.

The build now fails before packaging on unsupported API imports, unexpected
runtime libraries, wrong ABI/linker or insufficient page alignment. Bundles include
Go, SQLite, QR and NDK/toolchain notices. This is not the complete distribution
source/license audit. Nine host tests cover the installer and ELF audit policy.

Maintainers can build and verify without executing Android code on the host:

```sh
python3 scripts/build-release.py --ndk /path/to/android-ndk-r28c --version v0.1.0-dev.26 --arch arm64 --output dist/v0.1.0-dev.26
python3 scripts/verify-release.py --bundle dist/v0.1.0-dev.26/zombiebox-gateway-android-arm64.tar.gz --arch arm64 --ndk /path/to/android-ndk-r28c
# Repeat with --arch armv7 and the corresponding archive filename.
```

The verifier exercises the bootstrap's bounded extractor, per-file checksums and
installer validation, then independently repeats the ELF audit. The manual CI
workflow records this report before uploading candidate artifacts; it does not
publish a release. Actual Termux install/start/upgrade/SQLite/discovery/boot and
16-KiB-device execution remain in the deferred physical track.

## dev.27 increment

Pins the same 1080p negotiation core as Full. The preserved dev.26 Android bundles retain their original provenance; they were not relabeled as dev.27 artifacts. No new native runtime evidence or optional module completion is claimed.

## dev.29 increment

Pins the same audio-only Cast core without a fork. Existing dev.26 Bionic archives retain their provenance; optional MediaMTX packaging and native runtime acceptance remain open.
Product milestones and physical acceptance remain open.

## dev.30 increment

Pins the shared phone-media core with bounded temporary storage beside SQLite and existing FFmpeg tools. Existing dev.26 Bionic artifacts are unchanged; no new Android runtime claim.
Product milestones and deferred physical gates remain open.

## dev.31 increment

Pins the shared native-inventory validation/export core. Existing dev.26 Bionic archives retain their original provenance; they are not relabeled or claimed to contain this source.
Product milestone and physical/public distribution gates remain open.

## dev.32 increment

Pins the shared legacy phone-file container increment. New Android/Bionic candidate build evidence belongs to the workspace checkpoint; old archives retain their own version and source pins.
Product milestones, physical validation and public distribution remain open.

## dev.34 increment

Consumes dev.34 core pairing and remote-text implementation; native Bionic packaging is unchanged. Optional worker artifacts, Android runtime acceptance and publication remain open.

## dev.35 increment

Pins the same dev.35 queue/adaptation/listening implementation with a real core remote. No Linux binary or fork; Bionic runtime and optional prebuilt modules remain unverified.


## dev.37 increment

[Optional binary modules and status matrix](docs/optional-modules.md). Doctor now separates installed files, running/stopped services, runtime-version compatibility and unprobed account/media readiness.

## dev.40 reception and diagnostics increment

Optional doctor --network consumes the shared core endpoint report, redacts unsupported output and distinguishes old binary/timeout from verified reachability. Other optional module binary delivery remains open. Product milestones remain open.

[Shared endpoint diagnostic contract](https://github.com/ZombieBox-tv/zombiebox-gateway-core/blob/v0.1.0-dev.40/docs/endpoint-diagnostics.md).

## dev.41 guide and audio selection increment

Pins the shared capability-aware audio-selection core. Published dev.40 Android bundles retain their original identity; other optional binary modules remain open. Product and physical gates remain open.

Dev.42: pin the shared preferred-audio planner. Public core binaries remain dev.40; remaining optional prebuilt modules and Android runtime acceptance remain open.

## dev.43 navigation and functional media increment

Dev.43: optional doctor --media validates bounded decoded-frame evidence through the shared core without granting receiver/network support. Older binaries remain unavailable/unsupported. Other optional Node/Spotify/AirPlay binary modules and physical gates remain open.
