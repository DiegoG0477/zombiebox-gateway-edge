import hashlib
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "reviewed_notices",
    Path(__file__).resolve().parents[1] / "scripts/reviewed_notices.py",
)
notices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notices)


class ReviewedNoticeTests(unittest.TestCase):
    def test_review_preserves_notice_and_excludes_unlinked_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = b"// Copyright fixture\n// Permitted fixture\n\npackage keywrap\n"
            review = {
                ("example/module", "v1.0.0"): {
                    "package": "keywrap",
                    "noticeFile": "wrap.go",
                    "noticeLines": 2,
                    "license": "fixture",
                    "files": {"wrap.go": hashlib.sha256(source).hexdigest()},
                }
            }
            archive = root / "upstream.zip"
            with zipfile.ZipFile(archive, "w") as target:
                target.writestr("example/module@v1.0.0/keywrap/wrap.go", source)
                target.writestr("example/module@v1.0.0/unreviewed.go", "unrelated")
            with patch.object(notices, "REVIEWS", review):
                record = notices.collect_reviewed(
                    "example/module",
                    "v1.0.0",
                    {"example/module/keywrap"},
                    archive,
                    root / "subset.zip",
                    root / "notice.txt",
                )
                self.assertEqual(record["sourceScope"], "reviewed-package-subset")
                self.assertEqual(
                    (root / "notice.txt").read_text(),
                    "Copyright fixture\nPermitted fixture\n",
                )
                with zipfile.ZipFile(root / "subset.zip") as subset:
                    self.assertEqual(
                        subset.namelist(), ["example/module@v1.0.0/keywrap/wrap.go"]
                    )
                    self.assertEqual(subset.read(subset.namelist()[0]), source)
                for version, packages in (
                    ("v2.0.0", {"example/module/keywrap"}),
                    ("v1.0.0", {"example/module/keywrap", "example/module/other"}),
                    ("v1.0.0", set()),
                ):
                    with self.assertRaises(ValueError):
                        notices.collect_reviewed(
                            "example/module",
                            version,
                            packages,
                            archive,
                            root / "other.zip",
                            root / "other.txt",
                        )
                review[("example/module", "v1.0.0")]["files"]["wrap.go"] = "0" * 64
                with self.assertRaises(ValueError):
                    notices.collect_reviewed(
                        "example/module",
                        "v1.0.0",
                        {"example/module/keywrap"},
                        archive,
                        root / "other.zip",
                        root / "other.txt",
                    )
