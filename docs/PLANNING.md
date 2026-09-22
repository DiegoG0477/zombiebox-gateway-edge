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
