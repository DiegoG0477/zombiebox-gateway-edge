# Gateway Edge

One shared Go core, built natively in Termux/Bionic. Android 7+ remains the target subject to current native package availability; Fedora builds do not validate that runtime.

```sh
pkg install git golang clang termux-services ffmpeg
# Restore third_party/sources using make references on the development host before transferring,
# or install Python and run scripts/sync-upstreams.py on the Edge host.
bash gateway-edge/install-termux.sh --with-cast --with-youtube
```

The optional YouTube worker needs native Node >=22 and npm. The gateway requires Go >=1.25; the pinned MediaMTX 1.21.1 source requires Go >=1.26. `GOTOOLCHAIN=local` prevents an incompatible Linux toolchain download in Termux. MediaMTX is compiled from the locked source in a disposable copy, with [our Android build-constraint patch](../wrappers/mediamtx/android.patch). Raspberry Pi camera integration and the standalone HLS JavaScript player are omitted. Neither is used by Zombie. The reference clone is unchanged.

The installer creates stopped runit services. After starting Termux's service supervisor:

```sh
sv-enable zombied
sv-enable zombie-mediamtx
sv-enable zombie-youtube
```

Private files live under `~/.zombie/`. Edit `config/runtime.env` for the intended LAN address in `ZOMBIE_LISTEN` and `ZOMBIE_RTSP_LISTEN`; defaults are loopback. HLS/control endpoints remain loopback. The generated relay key is preserved. Gateway and MediaMTX share it; do not paste it into the TV client. An optional persistent pairing code can be added as `ZOMBIE_PAIRING_CODE` to this private file; otherwise the gateway prints an ephemeral operator code at startup.

`config/youtube.json` holds worker credentials. The installer creates a disabled matching entry in `config/providers.json` if absent. Enable it there after enabling the worker; existing provider configuration is preserved. Provider account credentials remain server-side. Native FFmpeg is used only for local media at this checkpoint.

No Docker or Linux runtime binary is installed. SQLite uses native CGO/Bionic `go-sqlite3`; Linux uses the pure-Go driver with the same domain/SQL code. Native service restart, Android ABI compatibility, sustained resource use and thermal behavior still need physical validation. Boot/wake locks and UxPlay feasibility remain open. Native Spotify/Threadfin package installers now exist; they still require physical validation. Local Rebrowser is unsupported on Edge V1.

The pinned MediaMTX Android dependency [anet](https://github.com/wlynxg/anet/tree/v0.0.5) requires `-checklinkname=0` on Go 1.23+. Only the MediaMTX build uses this upstream-documented flag. An Android ARM64 binary compiled successfully with Go 1.26.0 and the local patch on Fedora; that is a cross-compilation check, not Termux execution. The installer records installed tool versions in `~/.zombie/build-info.txt`. Revalidate before changing Go/anet versions.

Additional packages (run inside Termux):

```sh
bash gateway-edge/install-services.sh spotify threadfin
```

Install native Python, pkg-config, libogg, libvorbis, libflac and mpg123 decode
libraries before the Spotify build. The installer checks native metadata and
fails instead of downloading Linux binaries. Services start disabled; existing
provider credentials and direct IPTV lists are preserved. See each wrapper README.
