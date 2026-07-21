# FeedMine catalog updates

This public repository is FeedMine's **update channel** for its curated OPML
catalog. It is not an application backend: FeedMine reads, searches, filters,
and fetches sources from its own local catalog, and continues to work when this
repository or the network is unavailable.

## Layout

- `manifest.json` is the signed-off snapshot inventory and monotonic revision.
- `Feeds/` is the canonical OPML menu tree. Directory and file names define the
  menu order shown by the app.

At launch, the app renders from its last valid local snapshot and checks
`manifest.json` in the background. A newer revision is copied into a staging
directory, every OPML is checked against its SHA-256 and byte count, and the
local SQLite/FTS search catalog is rebuilt and validated. Only then is the
staged snapshot atomically activated. Network, XML, checksum, compilation, or
activation failures leave the previous local snapshot untouched.

Removing an OPML or a source here removes it only from FeedMine's managed
catalog. It does not remove user-imported feeds, bookmarks, reading history,
saved content, or user collections.

## Publishing

The source application repository owns the publisher:

```sh
python3 scripts/publish_catalog_update.py \
  --destination /path/to/feedmine-repo
```

The publisher synchronizes `Feeds/`, increments the revision, computes all
hashes, and writes the same bootstrap manifest into the next app build. Do not
edit a published revision in place; any catalog change must receive a higher
revision.

Before pushing, run:

```sh
python3 scripts/validate_manifest.py
```

