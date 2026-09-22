"""Release source inventory must fail closed for unverifiable linked modules."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from release_sources import linked_modules


class ReleaseSourcesTests(unittest.TestCase):
    def test_uses_linked_dependencies_only(self):
        self.assertEqual(
            linked_modules("file: go1.25.6\n\tdep\texample.org/a\tv1.0.0\th1:abc\n"),
            [("example.org/a", "v1.0.0", "h1:abc")],
        )

    def test_rejects_replaced_missing_or_duplicate_modules(self):
        module = "\tdep\texample.org/a\tv1.0.0\th1:abc\n"
        for metadata in (
            "",
            module + "\t=>\t../local\n",
            module + module,
            "\tdep\texample.org/a\tv1\n",
        ):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                linked_modules(metadata)
