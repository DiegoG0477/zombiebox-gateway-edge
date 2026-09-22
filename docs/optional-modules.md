# Optional Android binary modules

These modules supplement the Edge core. Installing one does not enable accounts,
start a receiver, or establish Android runtime acceptance. The core continues to
work with direct M3U/XMLTV without Threadfin.

| Module | Binary packaging at dev.38 | Remaining boundary |
|---|---|---|
| Threadfin 1.2.40 | ARMv7/ARM64 Android API24 PIE builder, source/dependency archives, ELF audit and compiler-free installer | Android execution, service/SSDP and workload acceptance deferred |
| MediaMTX 1.21.1 | ARMv7/ARM64 Android API24 PIE builder, sources/notices and compiler-free stopped-service installer | Android execution, RTSP/HLS/auth and thermal acceptance deferred; [public dev.38 assets](https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/tag/v0.1.0-dev.38) available |
| YouTube / TV receiver | Existing native source installation and pinned Node22 contract | Compiler-free compatible Node/runtime bundle still required |
| Spotify | Existing native source installation | Android native codec dependency closure and binary bundle |
| AirPlay / UxPlay | Experimental native source installation | Android GStreamer/OpenSSL/libplist closure and binary bundle |
| Rebrowser | Remote Full only | Local Edge browser is outside the supported baseline |

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
