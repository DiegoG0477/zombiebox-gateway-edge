# zombiebox-gateway-edge: component work

The product milestones relevant to this repository are M10, M11.
The local registry is a component projection of the workspace plan. Closing a
component task does not close a product-wide milestone or a physical validation gate.

Current increment: independent repository/build/dependency boundaries with filtered
history. Remaining feature development follows the ordered workspace audit:
tracks/subtitles and lifecycle; provider navigation/virtualization; measured
capabilities/native-first health; remote media adaptation; receiver finishing;
Edge operations and reproducible releases. Implement only this component's part,
and evolve shared protocol contracts in their owning repository.

Keep a separate validation track for hardware/account/latency/memory evidence.
Use development checkpoint tags until complete exit gates are evidenced. Hosted
issues/milestones can be attached to the shared GitHub Project once remotes exist.

## dev.49 public module status

[Dev.47](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.47)
publishes matching Core ARM64/ARMv7 and portable YouTube/TV receiver bundles for
Core dev.46. [Dev.48](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.48)
publishes both UxPlay/AirPlay ABI bundles with sources and SHA256. Their installer
checks the exact Core commit, native Termux packages, required RTP plugins and
both executables before stopping an existing AirPlay service. The service remains
stopped and disabled until configured. Local build, archive, ELF/API24 and remote
asset digest checks pass; Android runtime, GStreamer transitive closure, audio/
video, mDNS and thermal acceptance remain open.

Spotify prebuilt distribution remains open. The selected go-librespot revision
links `github.com/xlab/vorbis-go`, whose pinned source and repository do not carry
an explicit license. Cross-compiling both ABIs is insufficient to publish this
dependency. Replace the binding with a reviewed distributable implementation or
obtain an explicit upstream license before producing Edge binaries. This also
needs review for the already-published optional Full Spotify image. No product
milestone closes from these host and publication checks.

## dev.11 increment

Pins the same remote/browse core and adaptive YouTube worker. Native Termux/Bionic validation and operation lifecycle remain open.
No product milestone or physical/account gate is completed by this checkpoint.

## dev.12 increment

Pins the shared reception/Cast-budget implementation. Bionic operation and native UxPlay remain unverified/unimplemented respectively.

## dev.13 increment

Pins the same retry/live-TS implementation; no native lifecycle or Bionic evidence added.
No product milestone or physical/account gate closes with this checkpoint.

## dev.14 increment

Pins the shared HLS/DASH adapter; native FFmpeg and Termux/Bionic execution remain unverified.
The four requested block-1 changes are implemented; physical acceptance and broader product gates remain open.

## dev.16 increment

Pins shared core; native service lifecycle, boot/wake/doctor/update/uninstall and an explicitly experimental UxPlay source installer. Bionic execution remains unverified.
Product exit gates and physical/account acceptance remain open.

## dev.17 increment

Consumes dev.17 shared core and installs its first-party license/notice; no new Bionic runtime validation.

No product milestone or physical gate is closed.

## dev.18 increment

Dev.18: bounded persistent artwork derivatives, restart reuse, private cache keys, device/layout profiles and conditional HTTP caching. No physical milestone closes.

## dev.21 increment

Pins shared dev.21 network/search/state maintenance without forking the core or claiming native runtime acceptance.
No physical, account or product milestone closes.

Verification: installer/lifecycle shell syntax passes; the pinned core passes host Go and contract checks. Termux/Bionic execution remains unverified.

## dev.22 increment

Pins the same dev.22 receiver-coordination core; native Termux/Bionic execution remains unverified.
No product or physical acceptance gate closes.

Verification: native installer/lifecycle shell syntax passes; the shared core passes host checks. Termux/Bionic execution is unverified.

## dev.23 increment

Native shared discovery on LAN bindings; existing loopback configuration preserved.
Product exit gates and deferred physical acceptance remain open.


## dev.24 increment

Consumes the same companion core and installs its QR encoder license. This adds no Linux binary, Docker requirement or native Android execution evidence.
Full visual/capture policy, extended Remote, HEVC/4K and other product gates remain open; physical acceptance stays deferred.

Verification: Shell syntax and the exact core dependency pin pass on Fedora. No Termux/Bionic runtime claim is made.

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

## dev.34 implementation checkpoint

Consumes dev.34 core pairing and remote-text implementation; native Bionic packaging is unchanged. Optional worker artifacts, Android runtime acceptance and publication remain open.
Product exit gates and deferred physical acceptance remain open.

## dev.35 checkpoint

Pins the same dev.35 queue/adaptation/listening implementation with a real core remote. No Linux binary or fork; Bionic runtime and optional prebuilt modules remain unverified.
Product milestone completion still requires its recorded acceptance gates.


## dev.37 implementation checkpoint

Compiler-free Threadfin Android module installer/builder and separated module diagnostics. MediaMTX dependency notice and other optional binary modules remain open; no Android execution claim.

## dev.38 implementation checkpoint

Dev.38: MediaMTX compiler-free Android modules, pinned inline BSD notice review and source subset inventory. Other optional modules, Full distribution and physical acceptance remain open.

## dev.40 reception and diagnostics increment

Optional doctor --network consumes the shared core endpoint report, redacts unsupported output and distinguishes old binary/timeout from verified reachability. Other optional module binary delivery remains open. Product milestones remain open.

## dev.41 guide and audio selection increment

Pins the shared capability-aware audio-selection core. Published dev.40 Android bundles retain their original identity; other optional binary modules remain open. Product and physical gates remain open.

## dev.42 navigation and preferred-audio increment

Dev.42: pin the shared preferred-audio planner. Public core binaries remain dev.40; remaining optional prebuilt modules and Android runtime acceptance remain open.

## dev.43 navigation and functional media increment

Dev.43: optional doctor --media validates bounded decoded-frame evidence through the shared core without granting receiver/network support. Older binaries remain unavailable/unsupported. Other optional Node/Spotify/AirPlay binary modules and physical gates remain open.

## dev.44 authenticated HLS coverage pin

Consumes Core dev.44's host integration test for authenticated HLS alternate audio.
The Android/Bionic binaries and runtime behavior are unchanged. The existing
Threadfin/MediaMTX module assets keep their exact release identities; Node,
Spotify and AirPlay optional binary work and physical validation remain open.

## dev.45 — optional Node module implementation

Edge now has a portable JS builder for the locked YouTube catalog and TV receiver
workers, with matching npm tarballs and source receipts, plus a compiler-free
checksum-gated installer. It requires the installed Edge core to match the module's
Core commit, preserves credentials and installs stopped. The official Termux Node24
LTS is the candidate native runtime; host Node24 tests passed. Release assets,
Bionic execution and actual TV Code/YouTube service behavior remain separate gates.
Spotify and UxPlay still require native dependency/source closure.

## dev.46 — public Edge Node/Core artifact delivery

The dev.45 prerelease now carries matching source archives, checksums and binaries
for API24 ARM64/ARMv7 Core plus portable YouTube catalog/TV receiver workers. The
121 npm package tarballs were checked against lockfile SHA512, every installed
package has a notice inventory entry, Core ELF imports align with API24, and all
14 remote asset digests match local files. Both module downloads passed without
credentials; extraction, manifest validation and stopped-service installation
passed on a simulated host. Android/Bionic execution, accounts, DIAL reception and
Spotify/AirPlay native modules remain open. No product milestone closes.
