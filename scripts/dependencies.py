#!/usr/bin/env python3
"""Resolve or restore an explicitly pinned source dependency; never rewrite a checkout."""

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["path", "check", "fetch"])
    parser.add_argument("name")
    args = parser.parse_args()
    item = json.loads((ROOT / "dependencies.lock.json").read_text())["dependencies"][
        args.name
    ]
    override = os.environ.get(item["environment"])
    sibling = ROOT.parent / args.name
    path = (
        Path(override).resolve()
        if override
        else (sibling if sibling.is_dir() else ROOT / ".deps" / args.name)
    )
    if not (path / ".git").exists():
        if args.action != "fetch" or not item.get("remote"):
            raise SystemExit(
                f"Missing {args.name}. Provide {item['environment']} or configure its remote in dependencies.lock.json and run make deps."
            )
        if path.exists():
            raise SystemExit(f"Refusing to overwrite {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--no-checkout", "--", item["remote"], str(path)],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(path), "checkout", "--detach", item["commit"]], check=True
        )
    if args.action in ("check", "fetch"):
        actual = subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
        ).strip()
        if actual != item["commit"]:
            raise SystemExit(
                f"{args.name} is not at the pinned commit; checkout separately or explicitly update the lock."
            )
        dirty = subprocess.check_output(
            ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"],
            text=True,
        )
        if dirty:
            raise SystemExit(
                f"{args.name} contains tracked changes; commit or restore them before a reproducible build."
            )
    print(path)


if __name__ == "__main__":
    main()
