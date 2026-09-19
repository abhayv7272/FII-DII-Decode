#!/usr/bin/env python3
"""Audit whether timestamped forward context is ready for a frozen study.

This command does not fit a rule, join a next-session label, or report any
accuracy. It is a data-quality gate intended to stop premature threshold mining
while the new pre-open/intraday stores are still sparse.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fiidii.forward_audit import audit_forward_context  # noqa: E402


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _markdown(summary: dict) -> str:
    readiness = summary["readiness"]
    lines = [
        "# Forward Context Collection Readiness",
        "",
        "> Collection-quality audit only. This report evaluates no outcome, rule, prediction or accuracy.",
        "",
        f"- Generated: `{summary['generated_at_utc']}`",
        f"- Pre-open rows: **{summary['input_rows']['preopen']}**",
        f"- Intraday rows: **{summary['input_rows']['intraday']}**",
        f"- Sessions seen: **{summary['sessions_seen']}**",
        f"- Complete direct/timed sessions: **{summary['complete_sessions']}**",
        f"- Status: **{readiness['status']}**",
        "",
        "## Fixed gates",
        "",
        f"- Quality review only: `{readiness['quality_gate_sessions']}` complete sessions.",
        f"- Freeze the first study only after `{readiness['frozen_study_sessions']}` complete sessions: first 80 development, next 60 validation, next 60 confirmation.",
        f"- Promotion still needs `{readiness['promotion_forward_sessions']}` complete sessions, adding 60 untouched fresh-forward sessions after confirmation.",
        "- Session counts, not 15-minute-row counts, are used because captures within one session are correlated.",
        "",
        "## Collection failures",
        "",
    ]
    if summary["missing_required_columns"]:
        for name, missing in summary["missing_required_columns"].items():
            if missing:
                lines.append(f"- `{name}` missing columns: {', '.join(missing)}")
    if summary["failure_counts"]:
        lines.extend(f"- `{reason}`: {count}" for reason, count in summary["failure_counts"].items())
    elif not any(summary["missing_required_columns"].values()):
        lines.append("- None in the sessions currently present.")
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "A readiness state is not an accuracy result and does not authorise a production score change. Feature selection, label joins and trade/execution evaluation remain prohibited until the fixed collection gate is met.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument("--out", type=Path, default=ROOT / "reports" / "forward_context_readiness")
    args = parser.parse_args(argv)

    summary = audit_forward_context(
        _read_csv(args.data_dir / "preopen_snapshots.csv"),
        _read_csv(args.data_dir / "intraday_option_snapshots.csv"),
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    (args.out / "REPORT.md").write_text(_markdown(summary))
    print(json.dumps({
        "status": summary["readiness"]["status"],
        "complete_sessions": summary["complete_sessions"],
        "out": str(args.out),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
