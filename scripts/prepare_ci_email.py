from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[1]
DAILY = PROJECT / "reports" / "daily"


def tail(path: Path, lines: int = 120) -> str:
    if not path.exists():
        return "Log file not created."
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", default="unknown")
    parser.add_argument("--pipeline", default="unknown")
    args = parser.parse_args()
    DAILY.mkdir(parents=True, exist_ok=True)
    target = DAILY / "LATEST_EMAIL_REPORT.md"

    reports = sorted(DAILY.glob("*_professional_report.md"), key=lambda p: p.stat().st_mtime)
    if args.tests == "success" and args.pipeline == "success" and reports:
        shutil.copyfile(reports[-1], target)
        print(f"Prepared successful email report: {reports[-1].name}")
        return

    content = f"""# NIFTY PIPELINE FAILURE

**UTC time:** {datetime.now(timezone.utc).isoformat()}  
**Tests:** {args.tests}  
**Production pipeline:** {args.pipeline}

No trading decision should be used from this failed run. The safe decision is **WAIT / NO TRADE**.

## Test log tail

```text
{tail(PROJECT / 'test_output.log')}
```

## Production log tail

```text
{tail(PROJECT / 'production_output.log')}
```

Check GitHub Actions logs, provider availability, repository secrets and source-schema changes.
"""
    target.write_text(content, encoding="utf-8")
    print("Prepared failure email report")


if __name__ == "__main__":
    main()
