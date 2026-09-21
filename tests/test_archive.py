import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


class ArchiveTests(unittest.TestCase):
    def extract(self, entries):
        bootstrap = (Path(__file__).resolve().parents[1] / "install.sh").read_text()
        code = bootstrap.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "bundle.tar.gz"
            with tarfile.open(archive, "w:gz") as content:
                for name, kind in entries:
                    member = tarfile.TarInfo(name)
                    member.type = kind
                    member.size = 1 if kind == tarfile.REGTYPE else 0
                    member.linkname = "/tmp/outside"
                    content.addfile(
                        member, io.BytesIO(b"x") if member.isfile() else None
                    )
            return subprocess.run(
                [sys.executable, "-", str(archive), str(root / "output")],
                input=code,
                text=True,
                capture_output=True,
                timeout=5,
            ).returncode

    def test_regular_files(self):
        self.assertEqual(self.extract([("bin/zombied", tarfile.REGTYPE)]), 0)

    def test_traversal_links_duplicate_and_excessive_members(self):
        for entries in (
            [("../outside", tarfile.REGTYPE)],
            [("/absolute", tarfile.REGTYPE)],
            [("symlink", tarfile.SYMTYPE)],
            [("hardlink", tarfile.LNKTYPE)],
            [("same", tarfile.REGTYPE), ("same", tarfile.REGTYPE)],
            [(f"file-{index}", tarfile.REGTYPE) for index in range(257)],
        ):
            with self.subTest(entries=entries[:2]):
                self.assertNotEqual(self.extract(entries), 0)


if __name__ == "__main__":
    unittest.main()
