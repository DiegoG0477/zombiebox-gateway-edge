"""The Termux installer must reject an invalid channel before downloading binaries."""

import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstallChannelTests(unittest.TestCase):
    def test_invalid_channel_stops_before_archive_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "bin"
            tools.mkdir()
            for name, output in (
                ("getprop", "24"),
                ("dpkg", "aarch64"),
                ("pkg", ""),
            ):
                executable = tools / name
                executable.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}'\n")
                executable.chmod(0o755)
            calls = root / "curl-calls"
            curl = tools / "curl"
            curl.write_text(
                '#!/bin/sh\nprintf "%s\\n" "$*" >> "$CURL_CALLS"\nexec '
                + shlex.quote(shutil.which("curl"))
                + ' "$@"\n'
            )
            curl.chmod(0o755)
            channel = root / "channel.txt"
            channel.write_text("v0.1.0-dev.50/../../invalid\n")
            result = subprocess.run(
                [
                    "bash",
                    str(ROOT / "install.sh"),
                    "--repository",
                    "ZombieBox-tv/zombiebox-gateway-edge",
                ],
                env={
                    **os.environ,
                    "PREFIX": "/data/data/com.termux/files/usr",
                    "PATH": str(tools) + os.pathsep + os.environ["PATH"],
                    "ZOMBIE_INSTALL_CHANNEL_URL": channel.as_uri(),
                    "CURL_CALLS": str(calls),
                },
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("Invalid Edge release channel", result.stderr)
            self.assertEqual(len(calls.read_text().splitlines()), 1)
            self.assertIn(channel.as_uri(), calls.read_text())


if __name__ == "__main__":
    unittest.main()
