#!/usr/bin/env python3
"""Verify a built Edge archive using the bootstrap's real extraction/validation path."""

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from audit_android import audit

ROOT = Path(__file__).resolve().parents[1]


def verify(bundle, arch, ndk=None):
    if bundle.stat().st_size > 128 * 1024 * 1024:
        raise ValueError("Bundle exceeds the bootstrap download limit")
    checksum = bundle.with_name(bundle.name + ".sha256").read_text().split()
    if len(checksum) != 2 or checksum[1] != bundle.name:
        raise ValueError("Checksum must identify this archive")
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    if digest != checksum[0]:
        raise ValueError("Archive checksum mismatch")
    bootstrap = (ROOT / "install.sh").read_text()
    extractor = bootstrap.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    spec = importlib.util.spec_from_file_location(
        "installer", ROOT / "scripts/install-binary.py"
    )
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    with tempfile.TemporaryDirectory(prefix="zombie-edge-verify-") as temporary:
        package = Path(temporary) / "package"
        subprocess.run(
            [sys.executable, "-", str(bundle), str(package)],
            input=extractor,
            text=True,
            check=True,
            timeout=30,
        )
        manifest = installer.validate(package, arch, 24)
        if ndk is not None:
            actual = audit(package / "bin/zombied", ndk, arch)
            if actual != manifest.get("binaryAudit"):
                raise ValueError("Binary audit differs from the packaged evidence")
        return {
            "version": manifest["version"],
            "architecture": arch,
            "sha256": digest,
            "archiveBytes": bundle.stat().st_size,
            "binaryBytes": (package / "bin/zombied").stat().st_size,
            "fileCount": len(manifest["files"]),
            "coreCommit": manifest["coreCommit"],
            "edgeCommit": manifest["edgeCommit"],
            "edgeDirty": manifest["edgeDirty"],
            "binaryAudit": manifest.get("binaryAudit"),
            "extractionAndChecksumsPassed": True,
            "runtimeVerified": False,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--arch", choices=("armv7", "arm64"), required=True)
    parser.add_argument("--ndk", type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.bundle.resolve(), args.arch, args.ndk), indent=2))


if __name__ == "__main__":
    main()
