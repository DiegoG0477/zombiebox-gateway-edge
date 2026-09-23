# Optional Android binary modules

These modules supplement the Edge core. Installing one does not enable accounts,
start a receiver, or establish Android runtime acceptance. The core continues to
work with direct M3U/XMLTV without Threadfin.

| Module | Published or available packaging | Remaining boundary |
|---|---|---|
| Threadfin 1.2.40 | ARMv7/ARM64 Android API24 PIE builder, source/dependency archives, ELF audit and compiler-free installer | Android execution, service/SSDP and workload acceptance deferred |
| MediaMTX 1.21.1 | ARMv7/ARM64 Android API24 PIE builder, sources/notices and compiler-free stopped-service installer | Android execution, RTSP/HLS/auth and thermal acceptance deferred; [public dev.38 assets](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.38) available |
| YouTube / TV receiver | [Public dev.47](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.47) portable JS modules, source archives, checksum-gated stopped-service installer and matching Core for both ABIs | Validate Bionic Node, TV Code/DIAL and receiver behavior |
| Spotify | Existing native source installation; ARM64/ARMv7 cross-build candidates only | Replace the pinned Vorbis binding without an explicit license before binary distribution; then validate Android audio and accounts |
| AirPlay / UxPlay | [Public dev.48](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.48) ARMv7/ARM64 binaries, sources and compiler-free stopped-service installer | Validate Termux dependency closure, mDNS, PIN and audio/video on Android |
| Rebrowser | Remote Full only | Local Edge browser is outside the supported baseline |

## YouTube catalog and TV receiver module candidates

Both workers are portable JavaScript/WASM: fresh locked npm installs on Linux
Node24.18.0 had no `.node`, `.so` or ELF payloads, and all 14 wrapper tests passed.
`scripts/build-node-module.py` packages each worker with installed dependencies,
source files, exact npm tarballs checked against lockfile SHA512, source receipts
and checksums. `scripts/install-node-module.py` checks the payload, source asset
identity, Android API, matching installed Core commit and native Node version before
replacing a stopped runit service. It preserves credentials and leaves the provider
disabled. If native Node is absent, it installs Termux's prebuilt `nodejs-lts`; it
never uses a Linux Node executable.

These host-built modules and their matching Core are now published with verified
remote asset hashes. Bionic behavior remains unchecked. At this release's build,
Termux LTS is Node24.18.0; the separate TUR Node22 package is 22.22.1, below our security
floor. A later Termux package update can change the native runtime independently
of the frozen JS module, so doctor reports the actual version.

## AirPlay binary candidate

`scripts/build-airplay-module.py` builds the locked UxPlay source as an Android
PIE with internal mDNS. Its only source patch removes `-lpthread`, because Bionic
exports pthreads from libc. The package also carries the shared Go receiver
worker, licenses and a matching source archive. The build downloads exact
SHA256-pinned Termux headers/libraries from
`packaging/airplay-termux-libs.json`; these dynamic libraries are **not** bundled
with our module. The installer obtains their native packages through Termux,
checks the executable and worker before stopping an existing service, preserves
PIN/tokens and creates a stopped `zombie-airplay` service. It requires the exact
Core commit in the installed Edge bundle.

Install [dev.47 Core](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.47) first, then:

```sh
zombiebox module --module airplay --version v0.1.0-dev.48
zombiebox start zombie-airplay
```

The host ELF audit confirms Android API24 imports, ABI, PIE/interpreter and
16 KiB ARM64 or 4 KiB ARMv7 alignment. It checks direct Termux library imports,
but not the complete runtime transitive closure. Native GStreamer plugins,
receiver discovery, PIN, audio and video still require Android execution and
physical acceptance. The module does not silently enable AirPlay in Core.

## Threadfin installation

With a dev.37-or-newer core launcher, select the matching published checkpoint:

```sh
zombiebox module --module threadfin --version v0.1.0-dev.37
zombiebox start zombie-threadfin
zombiebox doctor
```

The pinned-version command requires the module assets to exist in that release;
it fails if they are absent. It never falls back to `latest`, Linux binaries or
source compilation. A locally transferred bundle uses an independently checked hash:

```sh
zombiebox module --module threadfin --bundle /path/zombiebox-threadfin-android-arm64.tar.gz --sha256 EXPECTED_SHA256
```

The installer verifies archive/file hashes, bounded extraction, upstream revision,
userland ABI, API and ELF interpreter before invoking the binary's help command or
stopping an old service. Configuration under `~/.zombie/threadfin` is retained;
versioned module files live under `~/.zombie/modules/threadfin`. Installation leaves
the service stopped. The management listener binds to `127.0.0.1:34400`; use a local
browser or an explicit secure tunnel to configure it. The gateway continues to use
the existing loopback Threadfin integration.

Threadfin's upstream binary updater is disabled in the staged source. Only a new
verified module bundle may replace the Android executable. The original reference
clone is unchanged, and the source archive includes the actual patched source.
Updating the core does not silently replace optional modules or their settings.

## Maintainer build

```sh
python3 scripts/build-module.py --module threadfin --arch arm64 --ndk /path/android-ndk-r28c --output dist/modules-dev37
# Repeat with --arch armv7.
```

The builder requires committed Edge/Core sources, the locked upstream checkout,
Go1.26.0 and NDK28.2.13676358. `--allow-dirty` explicitly creates a local candidate,
not a publishable checkpoint. No Android executable runs on the Linux build host.
Each binary archive identifies its matching source archive/hash, exact linked Go
modules, ABI/API import audit and recipe hash. Sources include patched upstream,
linked dependencies, Go standard library and first-party recipe licenses.

Finding a license file is an inventory check, not an automatic legal determination.
Distribution still requires review of the actual included source/notices. The
MediaMTX inline notice is handled by an exact package/source review below.

## MediaMTX installation and inline notice review

With a dev.38 launcher, install the published matching ABI module and start explicitly:

```sh
zombiebox module --module mediamtx --version v0.1.0-dev.38
zombiebox start zombie-mediamtx
zombiebox stop zombied
zombiebox start zombied
```

The installer preserves `config/mediamtx.yml` and `runtime.env`, reuses the core's
private relay key, and installs the module stopped. It enables core relay wiring
through `cast.enabled`; the running core must be restarted to read that setting.
The auth callback uses the configured core HTTP port. HLS and management remain
loopback-only; TCP RTSP defaults to `0.0.0.0:8554` for authorized phone publishing.
An existing `ZOMBIE_RTSP_LISTEN` override is preserved. Never expose these services
through public router port forwarding. This does not imply native AirPlay support.

The missing-LICENSE warning was a filename-only scanner limitation. The only
compiled OpenPGP package is `aes/keywrap`, whose `keywrap.go` and test carry the
complete Matthew Endsley BSD-2-Clause notice. The review pins the module version,
linked package set and all three package-file SHA256s. A new version, source change
or additional linked package fails packaging until reviewed. The notice is copied
verbatim (removing Go comment markers); cryptographic code is unchanged.

Corresponding sources include only this reviewed package from OpenPGP, its tests
and notice. Unrelated packages are excluded. `goSum` identifies the original module,
while `sourceSha256` identifies the explicitly labeled source subset; the archive
is not misrepresented as the complete Go proxy ZIP. Other dependencies retain their
original source ZIPs. All emitted dependency notices also accompany the source bundle.

Primary evidence: [pinned keywrap source and notice](https://github.com/benburkert/openpgp/blob/c2471f86866c/aes/keywrap/keywrap.go)
and [the gosrt import](https://github.com/datarhei/gosrt/blob/a77b40bb4b76b9d1018fa41c6a7fa6ed34af95bf/crypto/crypto.go).
The original module cache and reference clones are never modified.

## Functional media diagnostic (dev.43 source)

`zombiebox doctor --media` invokes the shared core's bounded local fixture,
remux/transcode and decoded-frame checks. It reads no provider configuration and
starts no service. Missing/old core flags remain unavailable. Software pipeline
success never establishes network, receiver, account or Android hardware support.
It can be combined with `--network` for the separate existing endpoint checks.
