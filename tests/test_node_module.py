"""Host checks for the compiler-free, exact-core Edge Node module path."""

import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/install-node-module.py"
spec = importlib.util.spec_from_file_location("install_node_module", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
builder_spec = importlib.util.spec_from_file_location(
    "build_node_module",
    Path(__file__).resolve().parents[1] / "scripts/build-node-module.py",
)
builder = importlib.util.module_from_spec(builder_spec)
builder_spec.loader.exec_module(builder)


class NodeModuleTests(unittest.TestCase):
    def test_runtime_floor_excludes_unpatched_and_untested_majors(self):
        for version, expected in (
            ("v22.22.1", False),
            ("v22.22.2", True),
            ("v23.10.0", False),
            ("v24.17.9", False),
            ("v24.18.0", True),
            ("v25.0.0", False),
            ("unavailable", False),
        ):
            self.assertEqual(module.node_compatible(version), expected)

    def test_archive_rejects_escape_before_extraction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "module.tar.gz"
            with tarfile.open(archive, "w:gz") as writer:
                entry = tarfile.TarInfo("../outside")
                entry.size = 4
                writer.addfile(entry, io.BytesIO(b"data"))
            checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                module.extract(archive, root / "staging", checksum)
            self.assertFalse((root / "outside").exists())

    def test_configuration_preserves_existing_secrets_and_disables_new_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            config = runtime / "config"
            config.mkdir()
            (config / "providers.json").write_text('{"plex":{"token":"keep"}}\n')
            module.configure("youtube-receiver", runtime)
            first = (config / "youtube-receiver.json").read_text()
            module.configure("youtube-receiver", runtime)
            self.assertEqual((config / "youtube-receiver.json").read_text(), first)
            providers = json.loads((config / "providers.json").read_text())
            self.assertEqual(providers["plex"]["token"], "keep")
            self.assertFalse(providers["youtube_receiver"]["enabled"])
            self.assertEqual(
                providers["youtube_receiver"]["token"], json.loads(first)["token"]
            )

    def test_manifest_rejects_mismatched_core_or_missing_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            (package / "module.json").write_text(
                json.dumps({"module": "youtube", "coreCommit": "other"})
            )
            with self.assertRaisesRegex(ValueError, "exact installed Edge core"):
                module.validate(package, "youtube", "expected")

    def test_unknown_npm_package_without_notice_blocks_distribution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dependency = root / "package/youtube/node_modules/unknown"
            dependency.mkdir(parents=True)
            (dependency / "package.json").write_text('{"license":"MIT"}\n')
            with self.assertRaisesRegex(ValueError, "Missing third-party notice"):
                builder.collect_notices(
                    [("node_modules/unknown", {"version": "1.0.0"})],
                    root / "package/youtube",
                    root / "package",
                    root / "sources",
                )


if __name__ == "__main__":
    unittest.main()
