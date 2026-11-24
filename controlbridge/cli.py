"""Offline CLI. No network access or cloud credentials are used."""

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .core import MAX_AGE_HOURS, RULE_VERSION, assess, timestamp, validate


def render(report, document=None):
    from .dashboard import render_dashboard
    return render_dashboard(report, document)


def run(input_path, output, as_of):
    raw = input_path.read_bytes()
    document = validate(json.loads(raw))
    results = [assess(item, as_of) for item in document["evidence"]]
    counts = Counter(row["result"] for row in results)
    report = {
        "schema_version": "1.0", "mode": "fixture",
        "as_of": as_of.isoformat(), "input_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": {key: counts[key] for key in ("pass", "fail", "unknown")},
        "assessments": results,
    }
    # A new directory per run preserves previous output and prevents input overwrite.
    output.mkdir(parents=True, exist_ok=False)
    (output / "evidence.json").write_bytes(raw)
    (output / "assessment.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    (output / "report.html").write_text(render(report, document), encoding="utf-8", newline="\n")
    manifest = {
        "application_version": __version__, "rule_version": RULE_VERSION,
        "mode": "fixture", "as_of": as_of.isoformat(),
        "freshness_hours": MAX_AGE_HOURS,
        "artifacts": {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                      for name in ("evidence.json", "assessment.json", "report.html")},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Assess synthetic storage configuration evidence")
    parser.add_argument("--input", type=Path, default=Path("fixtures/storage-demo.json"))
    parser.add_argument("--output", type=Path, default=None, help="New output directory; existing directories are refused")
    parser.add_argument("--as-of", type=timestamp, default=None, help="Explicit assessment time for reproducible historical fixtures")
    parser.add_argument("--gate", action="store_true", help="Exit 1 when any assessment is fail or unknown")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    output = args.output or Path("outputs") / now.strftime("run-%Y%m%dT%H%M%S%fZ")
    try:
        report = run(args.input, output, args.as_of or now)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Input/output error: {error}\n")
    print(json.dumps(report["summary"]))
    print(f"Report: {(output / 'report.html').resolve()}")
    return int(args.gate and any(row["result"] != "pass" for row in report["assessments"]))
