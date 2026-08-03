#!/usr/bin/env python3
"""Build a single catalog index JSON from OPML files for the
FeedMine Catalog Browser (/catalog page on wawasoft.net).

Generates catalog/catalog-index.json with:
- tree: topics → subcategories with feed counts and doc indices
- countries: flat list of countries with feed counts and doc indices
- docs: flat array of compact feed entries (short keys)
- stats: source/ country/ topic counts
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = ROOT / "catalog"

# ---------------------------------------------------------------------------
# Short-key doc entry — maps 1:1 from OPML attributes (see spec)
# ---------------------------------------------------------------------------
# DocEntry fields: t=title, d=description, kw=keywords, s=sourceId,
#   l=language, m=mediaKind, n=nature, a=activity, tp=topic, sc=subcategory


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    manifest_data = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    if manifest_data.get("schemaVersion") != 1:
        fail("manifest schemaVersion must be 1")

    entries = manifest_data.get("files")
    if not isinstance(entries, list):
        fail("manifest files must be a list")

    # Data structures
    docs: list[dict] = []
    topic_subcats: dict[str, dict[str, list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    country_feeds: dict[str, list[int]] = defaultdict(list)

    doc_index = 0

    for entry in entries:
        repo_path = entry.get("path", "")
        if not repo_path:
            continue

        opml_path = ROOT / repo_path
        if not opml_path.is_file():
            print(f"warning: missing file {repo_path}, skipping", file=sys.stderr)
            continue

        try:
            tree = ET.parse(opml_path)
        except ET.ParseError as exc:
            print(f"warning: skipping invalid XML {repo_path}: {exc}", file=sys.stderr)
            continue

        # Determine if this is a country OPML
        is_country = repo_path.startswith("Feeds/90_countries/")
        country_name = None
        if is_country:
            parts = Path(repo_path).parts
            if len(parts) >= 3:
                country_name = parts[2].replace("_", " ").title()

        for outline in tree.getroot().iter("outline"):
            attrs = outline.attrib
            if "feedmineSourceId" not in attrs:
                continue

            title = attrs.get("title") or attrs.get("text", "")
            if not title:
                continue

            doc = {
                "t": title,
                "d": attrs.get("description", ""),
                "kw": attrs.get("category", ""),
                "s": attrs["feedmineSourceId"],
                "l": attrs.get("language", ""),
                "m": attrs.get("feedmineMediaKind", ""),
                "n": attrs.get("feedmineNature", ""),
                "a": attrs.get("feedmineActivity", ""),
                "tp": attrs.get("feedmineTopic", ""),
                "sc": attrs.get("feedmineSubcategory", ""),
            }

            docs.append(doc)

            topic = doc["tp"]
            subcat = doc["sc"]

            if is_country and country_name:
                country_feeds[country_name].append(doc_index)
            else:
                topic_subcats[topic][subcat].append(doc_index)

            doc_index += 1

    # Build tree
    tree_list = []
    for topic_name in sorted(topic_subcats.keys()):
        subcats = topic_subcats[topic_name]
        sub_list = []
        total = 0
        for sc_name in sorted(subcats.keys()):
            indices = subcats[sc_name]
            total += len(indices)
            sub_list.append({"k": sc_name, "c": len(indices), "docs": indices})
        tree_list.append({"k": topic_name, "c": total, "sub": sub_list})

    # Build countries list
    countries_list = []
    for cname in sorted(country_feeds.keys()):
        indices = country_feeds[cname]
        countries_list.append({"k": cname, "c": len(indices), "docs": indices})

    # Stats — use manifest sourceCount for unique sources (avoids double-counting
    # global feeds that appear in multiple country OPMLs).
    stats = {
        "sources": manifest_data.get("sourceCount", doc_index),
        "placements": doc_index,
        "countries": len(countries_list),
        "topics": len(tree_list),
    }

    # Assemble index
    index = {
        "v": 1,
        "gen": manifest_data.get("generatedAt", ""),
        "stats": stats,
        "tree": tree_list,
        "docs": docs,
        "countries": countries_list,
    }

    # Write
    CATALOG_DIR.mkdir(exist_ok=True)
    output_path = CATALOG_DIR / "catalog-index.json"
    output_path.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )

    file_size_mb = output_path.stat().st_size / (1024 * 1024)
    print(
        f"Catalog index: {stats['sources']:,} unique sources, {doc_index:,} placements, "
        f"{len(tree_list)} topics, {len(countries_list)} countries "
        f"→ {output_path} ({file_size_mb:.1f} MB)"
    )


if __name__ == "__main__":
    main()
