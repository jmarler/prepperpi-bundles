#!/usr/bin/env bash
# Re-copy the appliance's bundles.py into tools/bundles_schema.py.
#
# Override SRC if your appliance checkout lives elsewhere:
#   SRC=/path/to/prepperpi/services/prepperpi-admin/app/bundles.py ./tools/sync-schema.sh
set -euo pipefail
src="${SRC:-../prepperpi/services/prepperpi-admin/app/bundles.py}"
dest="$(cd "$(dirname "$0")" && pwd)/bundles_schema.py"

if [ ! -f "$src" ]; then
    echo "error: source not found: $src" >&2
    echo "set SRC=/path/to/bundles.py and re-run." >&2
    exit 2
fi

banner='# VENDORED COPY — sync from the appliance source via tools/sync-schema.sh.
# Do not edit in place; edit upstream and re-sync, otherwise the validator
# diverges from what the appliance accepts at install time.

'
{
    printf '%s' "$banner"
    cat "$src"
} > "$dest"

echo "synced $dest from $src"
