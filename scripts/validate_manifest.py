#!/usr/bin/env python3
"""Validate snapshot inventory, hashes, paths, and OPML well-formedness."""

from __future__ import annotations

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schemaVersion") != 1:
        fail("schemaVersion must be 1")
    if not isinstance(manifest.get("revision"), int) or manifest["revision"] < 1:
        fail("revision must be a positive integer")
    if not isinstance(manifest.get("sourceCount"), int) or manifest["sourceCount"] < 1:
        fail("sourceCount must be positive")

    entries = manifest.get("files")
    if not isinstance(entries, list) or manifest.get("fileCount") != len(entries):
        fail("fileCount does not match files")

    paths: set[str] = set()
    for entry in entries:
        relative = entry.get("path", "")
        parts = Path(relative).parts
        if (
            not relative.startswith("Feeds/")
            or not relative.endswith(".opml")
            or relative.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
            or relative in paths
        ):
            fail(f"unsafe or duplicate path: {relative}")
        paths.add(relative)

        path = ROOT / relative
        if not path.is_file():
            fail(f"missing file: {relative}")
        data = path.read_bytes()
        if len(data) != entry.get("bytes"):
            fail(f"size mismatch: {relative}")
        if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
            fail(f"checksum mismatch: {relative}")
        try:
            ET.fromstring(data)
        except ET.ParseError as error:
            fail(f"invalid XML in {relative}: {error}")

    actual = {
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "Feeds").rglob("*.opml")
        if path.is_file()
    }
    if actual != paths:
        missing = sorted(actual - paths)
        stale = sorted(paths - actual)
        fail(f"inventory mismatch; unlisted={missing}, missing={stale}")

    print(
        f"valid revision {manifest['revision']}: "
        f"{manifest['fileCount']} OPML files, {manifest['sourceCount']} sources"
    )


if __name__ == "__main__":
    main()

