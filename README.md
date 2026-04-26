# prepperpi-bundles

Official bundle manifests for [PrepperPi](https://github.com/jmarler/prepperpi).

A "bundle" is a curated set of content (Kiwix ZIMs + map regions + static
files) that the admin console can install in one click. This repo holds the
official bundles; the appliance fetches them from here when online and falls
back to the copies baked into the image when offline.

You don't need to fork PrepperPi to ship a bundle. Host your own
`index.json` + manifest files on any HTTP(S) endpoint (a GitHub repo's raw
URL works fine) and your users can point their PrepperPi at it from the
admin console.

## Repo layout

```
.
├── index.json                       # lists the official manifests
├── manifests/
│   ├── starter.yaml
│   ├── complete.yaml
│   ├── medical.yaml
│   └── education.yaml
├── tools/
│   ├── bundles-validate             # standalone CLI validator
│   ├── bundles_schema.py            # vendored from the appliance
│   ├── sync-schema.sh               # re-vendor helper
│   └── tests/                       # validator unit tests
├── .github/workflows/validate.yml   # CI: runs the validator on every PR
├── LICENSE                          # MIT-0
└── README.md                        # this file
```

## index.json

The entry point for a bundle source. Lists the manifests this source
publishes:

```json
{
  "version": 1,
  "name": "Official PrepperPi bundles",
  "manifests": [
    {"id": "starter",   "url": "manifests/starter.yaml"},
    {"id": "complete",  "url": "manifests/complete.yaml"},
    {"id": "medical",   "url": "manifests/medical.yaml"},
    {"id": "education", "url": "manifests/education.yaml"}
  ]
}
```

`url` is resolved relative to the `index.json` URL, so a community source
hosted at `https://example.com/bundles/index.json` with `manifests/foo.yaml`
loads from `https://example.com/bundles/manifests/foo.yaml`.

`id` must be unique within a single source. Across sources the appliance
namespaces with `<source-id>:<bundle-id>` so the same id can appear in
multiple sources without collision.

## Manifest schema

```yaml
id: starter                              # required, [a-z0-9-]+, unique per source
name: Starter                            # required, user-facing
description: |
  A curated kit covering medical, repair, and survival fundamentals.
  Around 28 GB on disk after install.
license_notes: |                         # optional, surfaced in the UI
  Includes CC BY-NC-SA content (WikiHow, Khan Academy). Personal /
  educational use only — see https://kiwix.org for license details.

items:
  # --- Kiwix ZIM ---
  - kind: zim
    book_id: wikipedia_en_medicine_maxi
    # size_bytes and sha256 are NOT in the manifest for ZIMs — the
    # appliance resolves them from the live Kiwix OPDS catalog at
    # install time. This keeps manifests stable across Kiwix updates.

  # --- Map region (extracted on-Pi from a planet PMTiles) ---
  - kind: map_region
    region_id: US                        # ISO code from the shipped catalog

  # --- Static file (PDF, HTML page, archive.org download, etc.) ---
  - kind: static
    url: https://www.oism.org/nwss/example.pdf
    sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
    size_bytes: 18000000
    install_to: static/nwss-kearny.pdf   # relative to /srv/prepperpi/
```

### Field reference

| Field | Required | Notes |
|---|---|---|
| `id` | yes | Lowercase, hyphens; unique within a source. |
| `name` | yes | One-line user-facing title. |
| `description` | yes | Multi-line; markdown allowed in the future. |
| `license_notes` | no | If any item has a non-permissive license caveat, surface it here. |
| `items` | yes | At least one item. |

### Item kinds

#### `zim`

```yaml
- kind: zim
  book_id: wikipedia_en_medicine_maxi
```

Only `book_id` is required. The appliance looks the book up in its cached
Kiwix OPDS catalog and pulls `size_bytes`, `sha256`, and the metalink at
install time. If the catalog hasn't been refreshed yet (offline since first
boot), the appliance prompts the user to refresh it before installing the
bundle.

#### `map_region`

```yaml
- kind: map_region
  region_id: US
```

Only `region_id` is required. The appliance looks the region up in the
shipped maps catalog (`prepperpi-tiles/regions.json`) and runs the existing
`pmtiles extract` worker. The downloaded `.pmtiles` gets a sidecar JSON
recording the source URL + ETag/Last-Modified so the update notifier can
detect staleness later.

#### `static`

```yaml
- kind: static
  url: https://archive.org/download/...
  sha256: 0123...
  size_bytes: 18000000
  install_to: static/nwss-kearny.pdf
```

All four fields required. The URL must be HTTPS in production (HTTP allowed
for local testing). `install_to` is relative to `/srv/prepperpi/` and must
not contain `..` or absolute paths. Allowed prefixes: `static/`,
`zim/static/`, `user-content/`. The appliance verifies the SHA-256 after
download and will not mark the bundle installed if the hash mismatches.

## Computing SHA-256 for static items

```bash
curl -fsSL "https://example.com/your-file.pdf" | sha256sum
# 0123456789abcdef...  -
```

Or for a file you've already downloaded:

```bash
sha256sum your-file.pdf
```

Use the lowercase hex digest (no `0x` prefix) in the manifest.

## License caveats by content kind

If your bundle includes content under a non-permissive license, surface it
in the manifest's `license_notes` field. Some examples worth flagging:

- **Wikipedia / WikiMed / Stack Exchange**: CC BY-SA. Permissive; redistribution is fine if you preserve attribution and license.
- **WikiHow / Khan Academy / iFixit**: CC BY-NC-SA. **Non-commercial only.** A hobbyist Pi is fine; selling preloaded SD cards is not.
- **TED Talks**: CC BY-NC-ND. Same NC restriction; no derivative works.
- **Project Gutenberg / FEMA / US gov publications**: public domain.
- **Custom**: anything you pull from `archive.org` — check each item's individual page.

The appliance shows `license_notes` to the user before they confirm an
install. If your bundle includes NC content, say so plainly.

## Hosting your own bundle source

Anywhere that can serve `index.json` over HTTPS works:

- A GitHub repo: use `https://raw.githubusercontent.com/<user>/<repo>/main/index.json`.
- A static-site host (GitHub Pages, Cloudflare Pages, Netlify).
- Your own server (Caddy / nginx serving a directory).

End-users add your source from the admin console's Bundles page →
"Add bundle source" → paste the URL. Your bundles then appear alongside
the official ones, namespaced as `<your-source-id>:<bundle-id>`.

## Validating your manifests

The appliance JSON-schema-validates manifests at install time and
surfaces a specific error for each problem. To pre-flight your bundle
locally, this repo ships a standalone validator under `tools/`:

```bash
# Schema check (offline, no network):
python3 tools/bundles-validate manifests/

# Validate the index entry-point + every manifest it points at:
python3 tools/bundles-validate manifests/ index.json

# Resolution check against a Kiwix catalog + regions snapshot
# (catches retired ZIM book_ids and unknown map regions):
python3 tools/bundles-validate \
    --catalog kiwix-catalog.json \
    --regions regions.json \
    manifests/
```

Exit codes: `0` clean, `1` at least one failure, `2` usage error.

The validator depends only on `pyyaml` plus the Python stdlib. It uses
the appliance's actual schema parser, vendored as
`tools/bundles_schema.py`; refresh it from a local prepperpi checkout
with `tools/sync-schema.sh` whenever the appliance schema changes.

### CI for community bundle repos

If you're hosting your own bundle source in a Git repo, copy
`tools/` and `.github/workflows/validate.yml` from this repo, and the
exact same checks will run on every PR. Minimal workflow snippet:

```yaml
name: validate
on:
  pull_request:
    paths: ['manifests/**', 'index.json', 'tools/**']
  push:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install pyyaml
      - run: python3 tools/bundles-validate manifests/ index.json
      - run: python3 -m unittest discover -s tools/tests
```

## Submitting to the official bundles

PRs to this repo welcome — open an issue first to discuss scope. Bundle
inclusion criteria (rough):

- Content is freely redistributable (license-checked).
- The bundle has a clear, narrow theme that doesn't overlap heavily with
  an existing official bundle.
- Total size is reasonable (a few hundred GB at most for a full-comprehensive bundle; 1-50 GB for themed ones).

If your bundle is niche or has license caveats that don't fit the
"official" criteria, host it yourself — that's the whole point of the
multi-source design.

## License

The manifests in this repo are MIT-0 — use them however you like. The
*content* they reference has its own licenses; see each manifest's
`license_notes` field.
