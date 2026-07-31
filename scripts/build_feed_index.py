#!/usr/bin/env python3
"""Build sharded feed index from OPML files listed in manifest.json.

Reads every OPML file, extracts <outline> elements that carry a
feedmineSourceId, and writes sharded JSON files to index/{XX}.json
where XX is the first two hex characters of the source ID.

The output schema matches the FeedRecord interface consumed by the
Wawasoft website datasheet page (/feed?sourceId=<hash>).
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "index"

# ---------------------------------------------------------------------------
# OPML attribute -> JSON key mapping (1:1 with FeedRecord in feed-catalog.ts)
# ---------------------------------------------------------------------------
_ATTR_MAP: dict[str, str] = {
    "text": "title",
    "title": "title",  # title wins over text when both present (OPML spec)
    "description": "description",
    "xmlUrl": "xmlUrl",
    "htmlUrl": "htmlUrl",
    "language": "language",
    "category": "category",
    "feedmineSourceId": "feedmineSourceId",
    "feedmineTopic": "feedmineTopic",
    "feedmineSubcategory": "feedmineSubcategory",
    "feedmineNature": "feedmineNature",
    "feedmineActivity": "feedmineActivity",
    "feedmineArticlesFetched": "feedmineArticlesFetched",
    "feedmineDefaultEnabled": "feedmineDefaultEnabled",
    "feedmineMediaKind": "feedmineMediaKind",
    "feedmineLatestItemAt": "feedmineLatestItemAt",
}

# Fields that must be present for a feed to be indexed.
_REQUIRED_ATTRS = {"feedmineSourceId", "title", "xmlUrl"}


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def extract_feeds(opml_path: Path, repo_path: str) -> list[dict]:
    """Parse an OPML file and return a list of feed record dicts."""
    feeds: list[dict] = []

    try:
        tree = ET.parse(opml_path)
    except ET.ParseError as exc:
        print(f"warning: skipping invalid XML {repo_path}: {exc}", file=sys.stderr)
        return feeds

    root = tree.getroot()
    # Walk every <outline> element at any depth.
    for outline in root.iter("outline"):
        attrs = outline.attrib
        if "feedmineSourceId" not in attrs:
            # Category/group outline — skip.
            continue

        record: dict = {}

        for xml_attr, json_key in _ATTR_MAP.items():
            value = attrs.get(xml_attr)
            if value is not None:
                record[json_key] = value

        # htmlUrl is optional in OPML data — set to None when absent.
        record.setdefault("htmlUrl", None)

        # Use "title" if present; otherwise fall back to "text".
        if "title" not in record and "text" in attrs:
            record["title"] = attrs["text"]

        # Validate required fields.
        missing = _REQUIRED_ATTRS - set(record.keys())
        if missing:
            sid = attrs.get("feedmineSourceId", "?")
            print(
                f"warning: skipping feed {sid} in {repo_path} "
                f"(missing: {', '.join(sorted(missing))})",
                file=sys.stderr,
            )
            continue

        # Track which OPML file this feed came from.
        record["_opmlPath"] = repo_path

        feeds.append(record)

    return feeds


def main() -> None:
    manifest_data = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))

    if manifest_data.get("schemaVersion") != 1:
        fail("manifest schemaVersion must be 1")

    entries = manifest_data.get("files")
    if not isinstance(entries, list):
        fail("manifest files must be a list")

    # Parse all OPMLs and collect feeds into shard buckets.
    shards: dict[str, dict[str, dict]] = defaultdict(dict)
    total_feeds = 0
    total_files = 0

    for entry in entries:
        repo_path = entry.get("path", "")
        if not repo_path:
            continue

        opml_path = ROOT / repo_path
        if not opml_path.is_file():
            print(f"warning: missing file {repo_path}, skipping", file=sys.stderr)
            continue

        feeds = extract_feeds(opml_path, repo_path)
        total_files += 1

        for feed in feeds:
            source_id = feed["feedmineSourceId"]
            if len(source_id) < 2:
                print(
                    f"warning: short sourceId {source_id} in {repo_path}, skipping",
                    file=sys.stderr,
                )
                continue

            shard_key = source_id[:2].lower()
            shards[shard_key][source_id] = feed
            total_feeds += 1

    # Write shard files.
    INDEX_DIR.mkdir(exist_ok=True)

    shard_count = 0
    for shard_key, bucket in sorted(shards.items()):
        shard_path = INDEX_DIR / f"{shard_key}.json"
        shard_path.write_text(
            json.dumps(bucket, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        shard_count += 1

    # Summary.
    print(
        f"Indexed {total_feeds:,} feeds across {total_files} OPML files "
        f"→ {shard_count} shards in index/"
    )

    expected = manifest_data.get("sourceCount", 0)
    if total_feeds != expected:
        print(
            f"note: indexed {total_feeds:,} feeds but manifest sourceCount "
            f"is {expected:,} (delta: {total_feeds - expected:+,})"
        )


if __name__ == "__main__":
    main()
