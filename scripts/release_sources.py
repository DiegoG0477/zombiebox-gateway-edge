"""Collect corresponding Edge sources from the modules actually linked into the ELF."""

import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


def linked_modules(metadata):
    modules = []
    for line in metadata.splitlines():
        fields = line.split()
        if fields and fields[0] == "=>":
            raise ValueError("Release builds must not use replaced Go modules")
        if fields and fields[0] == "dep":
            if len(fields) != 4 or not fields[3].startswith("h1:"):
                raise ValueError("Linked module lacks a Go content checksum")
            modules.append(tuple(fields[1:]))
    if not modules or len(modules) != len(set(item[0] for item in modules)):
        raise ValueError("Missing or duplicate linked module inventory")
    return modules


def collect(binary, core, edge, env, output):
    metadata = subprocess.check_output(
        ["go", "version", "-m", str(binary)], env=env, text=True
    )
    modules = linked_modules(metadata)
    with tempfile.TemporaryDirectory(prefix="zombie-edge-sources-") as temporary:
        root = Path(temporary)
        dependencies = []
        for name, version, checksum in modules:
            record = json.loads(
                subprocess.check_output(
                    ["go", "mod", "download", "-json", name + "@" + version],
                    cwd=core / "gateway",
                    env=env,
                    text=True,
                )
            )
            if record.get("Sum") != checksum or record.get("Error"):
                raise ValueError("Source content does not match linked Go module")
            basename = re.sub(r"[^a-zA-Z0-9._-]", "_", name + "@" + version)
            shutil.copy2(record["Zip"], root / (basename + ".zip"))
            shutil.copy2(record["GoMod"], root / (basename + ".mod"))
            dependencies.append(dict(module=name, version=version, goSum=checksum))
        commits = {}
        for name, checkout in (("gateway-core", core), ("gateway-edge", edge)):
            if subprocess.check_output(
                ["git", "-C", str(checkout), "status", "--porcelain"]
            ).strip():
                raise ValueError("Source distribution requires clean repositories")
            commit = subprocess.check_output(
                ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
            ).strip()
            commits[name] = commit
            with (root / (name + ".tar")).open("wb") as stream:
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(checkout),
                        "archive",
                        "--prefix=" + name + "/",
                        commit,
                    ],
                    stdout=stream,
                    check=True,
                )
        go_root = Path(
            subprocess.check_output(["go", "env", "GOROOT"], env=env, text=True).strip()
        )
        # Include the toolchain's standard-library sources, including vendored code.
        with tarfile.open(root / "go-standard-library.tar.gz", "w:gz") as archive:
            for name in ("src", "LICENSE", "PATENTS", "VERSION"):
                archive.add(go_root / name, arcname="go/" + name)
        record = dict(
            schemaVersion=1,
            components=commits,
            modules=dependencies,
            goVersion=(go_root / "VERSION").read_text().splitlines()[0],
            systemDependencies="Android libc/libdl/libm/liblog; supplied by Android, not this bundle",
            scope="Edge core only; FFmpeg and optional receiver modules are separate installations",
        )
        (root / "sources.json").write_text(json.dumps(record, indent=2) + "\n")
        (root / "BUILDING.md").write_text(
            "# Rebuild the Edge core\n\n"
            "Extract gateway-core.tar and gateway-edge.tar as sibling directories. "
            "Follow gateway-edge/README.md and scripts/build-release.py with the "
            "pinned Go 1.25.6 and NDK 28.2.13676358. No signing secret is required. "
            "Module ZIPs are the Go proxy source archives matching linked ELF "
            "checksums; their contents retain upstream licenses. Android system "
            "libraries and external Termux packages are not redistributed here.\n"
        )
        (root / "SHA256SUMS").write_text(
            "".join(
                hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name + "\n"
                for path in sorted(root.iterdir())
            )
        )
        # Each ABI gets its own source closure, tied to its actual linked modules.
        with tarfile.open(output, "x:gz") as archive:
            for path in sorted(root.iterdir()):
                archive.add(path, arcname=path.name, recursive=False)
    return {
        "name": output.name,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
