import hashlib
import importlib.util
import io
import json
import struct
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "modules", ROOT / "scripts/install-module.py"
)
modules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modules)


class ModuleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.package = self.root / "package"
        self.package.mkdir()
        for name in (
            "bin/threadfin",
            "licenses/upstream-LICENSE",
            "licenses/go-LICENSE",
            "licenses/ndk-NOTICE",
            "licenses/ndk-NOTICE.toolchain",
        ):
            target = self.package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fixture")
        elf = bytearray(160)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<HH", elf, 16, 3, 183)
        struct.pack_into("<Q", elf, 32, 64)
        struct.pack_into("<HH", elf, 54, 56, 1)
        struct.pack_into("<I", elf, 64, 3)
        struct.pack_into("<Q", elf, 72, 120)
        struct.pack_into("<Q", elf, 96, 21)
        elf[120:141] = b"/system/bin/linker64\0"
        (self.package / "bin/threadfin").write_bytes(elf)
        self.record = dict(
            schemaVersion=1,
            platform="android",
            architecture="arm64",
            minApi=24,
            module="threadfin",
            upstreamCommit=modules.MODULES["threadfin"],
            sourceArchive=dict(
                name="zombiebox-threadfin-android-arm64-sources.tar.gz", sha256="a" * 64
            ),
        )
        self.save()

    def save(self):
        self.record["files"] = {
            str(p.relative_to(self.package)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.package.rglob("*")
            if p.is_file() and p.name != "module.json"
        }
        (self.package / "module.json").write_text(json.dumps(self.record))

    def test_contract_and_abi(self):
        modules.validate(self.package, "threadfin", "arm64", 24)
        for module, arch, api in (
            ("threadfin", "armv7", 24),
            ("threadfin", "arm64", 23),
            ("mediamtx", "arm64", 24),
        ):
            with (
                self.subTest(module=module, arch=arch, api=api),
                self.assertRaises(ValueError),
            ):
                modules.validate(self.package, module, arch, api)
        self.record["upstreamCommit"] = "b" * 40
        self.save()
        with self.assertRaises(ValueError):
            modules.validate(self.package, "threadfin", "arm64", 24)

    def test_corruption_precedes_any_process_or_service_change(self):
        (self.package / "bin/threadfin").write_bytes(b"changed")
        with (
            patch.object(modules.subprocess, "run") as run,
            self.assertRaises(ValueError),
        ):
            modules.install(
                self.package,
                "threadfin",
                "arm64",
                24,
                self.root / "runtime",
                self.root / "prefix",
            )
        run.assert_not_called()

    def test_install_preserves_configuration_and_is_stopped(self):
        runtime, prefix = self.root / "runtime", self.root / "prefix"
        (runtime / "bin").mkdir(parents=True)
        (runtime / "bin/zombied").write_text("core")
        (runtime / "threadfin").mkdir()
        config = runtime / "threadfin/settings.json"
        config.write_text("private fixture")
        with patch.object(modules.subprocess, "run") as run:
            modules.install(self.package, "threadfin", "arm64", 24, runtime, prefix)
            self.assertEqual(run.call_count, 1)  # Only the Android -h smoke; no start.
        self.assertEqual(config.read_text(), "private fixture")
        self.assertTrue((prefix / "var/service/zombie-threadfin/down").exists())
        self.assertEqual(
            (runtime / "bin/threadfin").read_bytes(),
            (self.package / "bin/threadfin").read_bytes(),
        )

    def test_mediamtx_preserves_private_config_and_installs_stopped(self):
        (self.package / "bin/threadfin").rename(self.package / "bin/mediamtx")
        (self.package / "mediamtx.yml").write_text("packaged config")
        self.record.update(
            module="mediamtx",
            upstreamCommit=modules.MODULES["mediamtx"],
            sourceArchive=dict(
                name="zombiebox-mediamtx-android-arm64-sources.tar.gz", sha256="b" * 64
            ),
        )
        self.save()
        runtime, prefix = self.root / "runtime", self.root / "prefix"
        (runtime / "bin").mkdir(parents=True)
        (runtime / "bin/zombied").write_text("core")
        (runtime / "config").mkdir()
        config = runtime / "config/mediamtx.yml"
        config.write_text("existing private config")
        environment = runtime / "config/runtime.env"
        environment.write_text(
            "ZOMBIE_LISTEN=0.0.0.0:8099\nZOMBIE_RELAY_ADMIN_TOKEN=private\n"
        )
        with patch.object(modules.subprocess, "run") as run:
            modules.install(self.package, "mediamtx", "arm64", 24, runtime, prefix)
            self.assertEqual(run.call_count, 1)
        service = prefix / "var/service/zombie-mediamtx"
        self.assertTrue((service / "down").exists())
        self.assertTrue((runtime / "config/cast.enabled").exists())
        self.assertEqual(config.read_text(), "existing private config")
        self.assertIn("ZOMBIE_LISTEN=0.0.0.0:8099", environment.read_text())
        script = (service / "run").read_text()
        self.assertIn("${listen##*:}/internal/relay/auth", script)
        self.assertIn("MTX_HLSADDRESS=127.0.0.1:8888", script)
        self.assertNotIn("TOKEN=private", script)
        self.assertFalse((runtime / "threadfin").exists())

    def test_mediamtx_requires_packaged_configuration(self):
        (self.package / "bin/threadfin").rename(self.package / "bin/mediamtx")
        self.record.update(
            module="mediamtx", upstreamCommit=modules.MODULES["mediamtx"]
        )
        self.save()
        with self.assertRaises(ValueError):
            modules.validate(self.package, "mediamtx", "arm64", 24)

    def test_archive_rejects_traversal_links_duplicates_and_corruption(self):
        for names, kind in (
            (["../escape"], tarfile.REGTYPE),
            (["link"], tarfile.SYMTYPE),
            (["same", "same"], tarfile.REGTYPE),
        ):
            archive = self.root / "fixture.tar.gz"
            with tarfile.open(archive, "w:gz") as target:
                for name in names:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.size = 1 if member.isfile() else 0
                    member.linkname = "/tmp/outside"
                    target.addfile(
                        member, io.BytesIO(b"x") if member.isfile() else None
                    )
            checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                modules.extract(archive, self.root / "output", checksum)
            with self.assertRaises(ValueError):
                modules.extract(archive, self.root / "output", "a" * 64)
