import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from controlbridge.cli import main, render, run
from controlbridge.core import assess, timestamp, validate

ROOT = Path(__file__).resolve().parents[1]
AS_OF = timestamp("2026-11-16T10:00:00Z")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads((ROOT / "fixtures/storage-demo.json").read_text())
        self.item = copy.deepcopy(self.document["evidence"][0])

    def test_demo_outcomes(self):
        validate(self.document)
        self.assertEqual([assess(item, AS_OF)["result"] for item in self.document["evidence"]],
                         ["pass", "fail", "unknown", "unknown", "unknown"])

    def test_freshness_boundary(self):
        for time, expected in (("2026-11-15T10:00:00Z", "pass"),
                               ("2026-11-15T09:59:59Z", "unknown"),
                               ("2026-11-16T10:00:01Z", "unknown")):
            with self.subTest(time=time):
                self.item["collected_at"] = time
                self.assertEqual(assess(self.item, AS_OF)["result"], expected)

    def test_error_cannot_pass_even_with_safe_property(self):
        self.item["collection_status"] = "error"
        self.assertEqual(assess(self.item, AS_OF)["result"], "unknown")

    def test_null_is_unknown(self):
        self.item["properties"]["allowBlobPublicAccess"] = None
        self.assertEqual(assess(self.item, AS_OF)["result"], "unknown")

    def test_invalid_boolean_types_rejected(self):
        for value in ("false", 0, 1, [], {}):
            with self.subTest(value=value):
                self.document["evidence"][0]["properties"]["allowBlobPublicAccess"] = value
                with self.assertRaises(ValueError):
                    validate(self.document)

    def test_empty_inventory_rejected(self):
        self.document["evidence"] = []
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_duplicate_ids_rejected(self):
        self.document["evidence"].append(self.item)
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_timezone_required_and_normalised(self):
        with self.assertRaises(ValueError):
            timestamp("2026-11-16T10:00:00")
        self.assertEqual(timestamp("2026-11-16T11:00:00+01:00"), AS_OF)

    def test_live_mode_rejected(self):
        self.document["mode"] = "live"
        with self.assertRaises(ValueError):
            validate(self.document)

    def test_bundle_hashes_and_html_escaping(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "run"
            report = run(ROOT / "fixtures/storage-demo.json", output, AS_OF)
            self.assertEqual(report["summary"], {"pass": 1, "fail": 1, "unknown": 3})
            manifest = json.loads((output / "manifest.json").read_text())
            for name, digest in manifest["artifacts"].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            report["assessments"][0]["resource_id"] = '<script>alert("x")</script>'
            self.assertNotIn("<script>", render(report))
            self.assertIn("&lt;script&gt;", render(report))
            with self.assertRaises(FileExistsError):
                run(ROOT / "fixtures/storage-demo.json", output, AS_OF)

    def test_gate_returns_failure_for_mixed_demo(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(main(["--input", str(ROOT / "fixtures/storage-demo.json"),
                                   "--output", str(Path(folder) / "gate"),
                                   "--as-of", AS_OF.isoformat(), "--gate"]), 1)

    def test_dashboard_preserves_evidence_and_escapes_untrusted_source(self):
        self.document['evidence'][0]['source'] = '</pre><script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder) / 'fixture.json'
            fixture.write_text(json.dumps(self.document), encoding='utf-8')
            output = Path(folder) / 'run'
            run(fixture, output, AS_OF)
            page = (output / 'report.html').read_text(encoding='utf-8')
            self.assertNotIn('</pre><script>alert(1)</script>', page)
            self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', page)
            self.assertEqual(json.loads((output / 'evidence.json').read_text()), self.document)
            self.assertIn('2026-11-14T09:00:00Z', page)
            self.assertIn('Evidence exceeds the local lab freshness policy', page)


if __name__ == "__main__":
    unittest.main()
