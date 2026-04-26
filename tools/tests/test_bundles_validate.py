"""End-to-end tests for the bundles-validate CLI.

Run from the bundles repo root:
    python3 -m unittest discover -s tools/tests
or:
    python3 -m unittest tools.tests.test_bundles_validate
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "tools" / "bundles-validate"


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


CLEAN_MANIFEST = textwrap.dedent("""\
    id: smoke-test
    name: Smoke Test
    description: A clean manifest used by the test suite.
    items:
      - kind: zim
        book_id: wikipedia_en_medicine_mini
      - kind: map_region
        region_id: US
""")

BROKEN_YAML = textwrap.dedent("""\
    id: broken
    name: Broken
    items: [
""")

MISSING_FIELD = textwrap.dedent("""\
    id: nameless
    description: missing the required `name`
    items:
      - kind: zim
        book_id: wikipedia_en_medicine_mini
""")

DEAD_BOOK_MANIFEST = textwrap.dedent("""\
    id: dead-book
    name: Dead Book
    items:
      - kind: zim
        book_id: this_book_does_not_exist_anywhere
""")

FAKE_CATALOG = {
    "books": [
        {
            "name": "wikipedia_en_medicine",
            "title": "Wikipedia: Medicine",
            "filename": "wikipedia_en_medicine_mini_2026-04.zim",
            "size_bytes": 1024,
            "url": "https://example.invalid/zim/wikipedia_en_medicine_mini_2026-04.zim",
            "updated": "2026-04-01",
        },
    ]
}

FAKE_REGIONS = {
    "countries": [
        {"id": "US", "name": "United States", "estimated_bytes": 100_000_000},
    ]
}


class ValidateCleanManifestTests(unittest.TestCase):
    def test_clean_manifest_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "clean.yaml"
            p.write_text(CLEAN_MANIFEST, encoding="utf-8")
            r = _run(str(p))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("[OK]", r.stdout)
            self.assertIn("1 OK, 0 FAIL", r.stdout)


class ValidateRejectionTests(unittest.TestCase):
    def test_rejects_yaml_syntax_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "broken.yaml"
            p.write_text(BROKEN_YAML, encoding="utf-8")
            r = _run(str(p))
            self.assertEqual(r.returncode, 1)
            self.assertIn("[FAIL]", r.stdout)
            self.assertIn("YAML parse failed", r.stdout)

    def test_rejects_missing_required_field(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "nameless.yaml"
            p.write_text(MISSING_FIELD, encoding="utf-8")
            r = _run(str(p))
            self.assertEqual(r.returncode, 1)
            self.assertIn("`name`", r.stdout)


class ValidateResolutionTests(unittest.TestCase):
    def test_resolves_against_catalog_when_provided(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            manifest = tdp / "clean.yaml"
            manifest.write_text(CLEAN_MANIFEST, encoding="utf-8")
            catalog = tdp / "catalog.json"
            catalog.write_text(json.dumps(FAKE_CATALOG), encoding="utf-8")
            regions = tdp / "regions.json"
            regions.write_text(json.dumps(FAKE_REGIONS), encoding="utf-8")
            r = _run(
                "--catalog", str(catalog),
                "--regions", str(regions),
                str(manifest),
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 OK, 0 FAIL", r.stdout)

    def test_flags_dead_book_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            manifest = tdp / "dead.yaml"
            manifest.write_text(DEAD_BOOK_MANIFEST, encoding="utf-8")
            catalog = tdp / "catalog.json"
            catalog.write_text(json.dumps(FAKE_CATALOG), encoding="utf-8")
            r = _run("--catalog", str(catalog), str(manifest))
            self.assertEqual(r.returncode, 1)
            self.assertIn("not found in the Kiwix catalog", r.stdout)

    def test_flags_unknown_region(self) -> None:
        bad_region = textwrap.dedent("""\
            id: bad-region
            name: Bad Region
            items:
              - kind: map_region
                region_id: ZZ
        """)
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            manifest = tdp / "bad.yaml"
            manifest.write_text(bad_region, encoding="utf-8")
            regions = tdp / "regions.json"
            regions.write_text(json.dumps(FAKE_REGIONS), encoding="utf-8")
            r = _run("--regions", str(regions), str(manifest))
            self.assertEqual(r.returncode, 1)
            self.assertIn("not found in the maps catalog", r.stdout)


class ValidateDiscoveryTests(unittest.TestCase):
    def test_validates_directory_recursively(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "a").mkdir()
            (tdp / "a" / "one.yaml").write_text(
                CLEAN_MANIFEST.replace("smoke-test", "one"), encoding="utf-8"
            )
            (tdp / "two.yaml").write_text(
                CLEAN_MANIFEST.replace("smoke-test", "two"), encoding="utf-8"
            )
            r = _run(str(tdp))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("2 OK, 0 FAIL", r.stdout)

    def test_validates_index_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            (tdp / "manifests").mkdir()
            (tdp / "manifests" / "smoke.yaml").write_text(
                CLEAN_MANIFEST, encoding="utf-8"
            )
            index = tdp / "index.json"
            index.write_text(json.dumps({
                "version": 1,
                "name": "Test Source",
                "manifests": [
                    {"id": "smoke-test", "url": "manifests/smoke.yaml"},
                ],
            }), encoding="utf-8")
            r = _run(str(index))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("1 manifest(s)", r.stdout)
            self.assertIn("smoke-test", r.stdout)
            self.assertIn("1 OK, 0 FAIL", r.stdout)

    def test_unreachable_path_returns_2(self) -> None:
        r = _run("/nonexistent/path/manifest.yaml")
        self.assertEqual(r.returncode, 2)
        self.assertIn("path not found", r.stderr)


if __name__ == "__main__":
    unittest.main()
