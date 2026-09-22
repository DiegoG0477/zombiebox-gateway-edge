import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "audit", ROOT / "scripts/audit_android.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AndroidAuditTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.binary = Path(self.temporary.name) / "zombied"
        elf = bytearray(160)
        elf[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<HH", elf, 16, 3, 183)
        struct.pack_into("<Q", elf, 32, 64)
        struct.pack_into("<HH", elf, 54, 56, 1)
        struct.pack_into("<I", elf, 64, 3)
        struct.pack_into("<Q", elf, 72, 120)
        struct.pack_into("<Q", elf, 96, 21)
        elf[120:141] = b"/system/bin/linker64\0"
        self.binary.write_bytes(elf)
        self.library = "libc.so"
        self.alignment = "0x4000"
        self.imports = "1: 000000 0 FUNC GLOBAL DEFAULT UND read@LIBC\n"

    def readelf(self, tool, path, option):
        if option == "-d":
            return f"0x00001 (NEEDED) Shared library: [{self.library}]"
        if option == "-l":
            return f"LOAD 0x0000 0x0000 0x0000 0x0010 0x0010 R E {self.alignment}"
        if path == self.binary:
            return self.imports
        return "1: 000100 10 FUNC GLOBAL DEFAULT 5 read@@LIBC\n"

    def check(self):
        with patch.object(audit, "readelf", self.readelf):
            return audit.audit(self.binary, Path("unused-ndk"), "arm64")

    def test_api24_and_optional_weak_import(self):
        self.imports += "2: 0000 0 FUNC WEAK DEFAULT UND optional_future_api\n"
        report = self.check()
        self.assertTrue(report["api24ImportsSatisfied"])
        self.assertFalse(report["runtimeVerified"])

    def test_new_or_unavailable_strong_api_rejected(self):
        self.imports += "2: 0000 0 FUNC GLOBAL DEFAULT UND read@LIBC_O\n"
        with self.assertRaisesRegex(ValueError, "absent from API24"):
            self.check()

    def test_host_library_and_small_pages_rejected(self):
        self.library = "libc.so.6"
        with self.assertRaisesRegex(ValueError, "Unexpected runtime"):
            self.check()
        self.library = "libc.so"
        self.alignment = "0x1000"
        with self.assertRaisesRegex(ValueError, "page-size"):
            self.check()
