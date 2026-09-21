import hashlib
import importlib.util
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "installer", ROOT / "scripts/install-binary.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.package = self.root / "package"
        for name in (
            "bin/zombied",
            "edge.sh",
            "install.sh",
            "scripts/doctor.py",
            "scripts/install-binary.py",
            "LICENSE",
            "NOTICE",
            "licenses/go-qrcode-LICENSE",
            "runtime/zombied.sh",
            "runtime/zombiebox.sh",
        ):
            target = self.package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture")
        for name in (
            "baseline-360.mp4",
            "baseline-480.mp4",
            "main-720.mp4",
            "high-720.mp4",
            "high-1080.mp4",
            "aac.m4a",
            "baseline.ts",
            "fragmented.mp4",
        ):
            target = self.package / "probes" / name
            target.parent.mkdir(exist_ok=True)
            target.write_bytes(b"fixture")
        elf = bytearray(160)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<HH", elf, 16, 3, 183)
        struct.pack_into("<Q", elf, 32, 64)
        struct.pack_into("<HH", elf, 54, 56, 1)
        struct.pack_into("<I", elf, 64, 3)
        struct.pack_into("<Q", elf, 72, 120)
        struct.pack_into("<Q", elf, 96, 21)
        elf[120:141] = b"/system/bin/linker64\x00"
        (self.package / "bin/zombied").write_bytes(elf)
        self.manifest = {
            "schemaVersion": 1,
            "version": "v0.1.0-test.1",
            "platform": "android",
            "architecture": "arm64",
            "minApi": 24,
            "coreCommit": "a" * 40,
        }
        self.save_manifest()

    def save_manifest(self):
        self.manifest["files"] = {
            str(path.relative_to(self.package)): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in self.package.rglob("*")
            if path.is_file() and path.name != "release.json"
        }
        (self.package / "release.json").write_text(json.dumps(self.manifest))

    def test_native_contract_and_wrong_userland(self):
        installer.validate(self.package, "arm64", 24)
        for arch, api in (("armv7", 24), ("arm64", 23), ("x86", 30)):
            with self.assertRaises(ValueError):
                installer.validate(self.package, arch, api)

    def test_linux_or_wrong_elf_cannot_be_labeled_android(self):
        (self.package / "bin/zombied").write_bytes(b"linux binary")
        self.save_manifest()
        with self.assertRaises(ValueError):
            installer.validate(self.package, "arm64", 30)

    def test_corruption_precedes_service_stop(self):
        (self.package / "bin/zombied").write_bytes(b"changed")
        with (
            patch.dict(os.environ, {"PREFIX": str(self.root / "prefix")}),
            patch.object(installer.subprocess, "run") as run,
        ):
            with self.assertRaises(ValueError):
                installer.install(self.package, "arm64", 30, "local", "")
            run.assert_not_called()

    def test_reinstallation_preserves_private_data(self):
        home = self.root / "home"
        prefix = self.root / "prefix"
        (prefix / "bin").mkdir(parents=True)
        with (
            patch.dict(os.environ, {"PREFIX": str(prefix)}),
            patch.object(installer.Path, "home", return_value=home),
            patch.object(installer.subprocess, "run"),
        ):
            installer.install(self.package, "arm64", 30, "local", "")
            runtime = home / ".zombie"
            config = runtime / "config/providers.json"
            config.write_text('{"private":"keep"}')
            (runtime / "state/gateway.db").write_bytes(b"private database")
            environment = (runtime / "config/runtime.env").read_bytes()
            installer.install(self.package, "arm64", 30, "local", "")
            self.assertEqual(config.read_text(), '{"private":"keep"}')
            self.assertEqual(
                (runtime / "state/gateway.db").read_bytes(), b"private database"
            )
            self.assertEqual((runtime / "config/runtime.env").read_bytes(), environment)
            self.assertTrue((runtime / "bin/zombied").is_file())


if __name__ == "__main__":
    unittest.main()
