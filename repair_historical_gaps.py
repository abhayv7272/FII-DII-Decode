from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data_hub import append_history, bhavcopy_filtered, participant_nselib, summarize_options, summarize_participant


def main() -> None:
    options = pd.read_csv("data/historical_option_features.csv")
    futures = pd.read_csv("data/historical_futures_features.csv")
    missing = sorted(set(futures.date.astype(str)) - set(options.date.astype(str)))
    repaired: list[str] = []
    failed: list[dict[str, str]] = []
    participant_failed: list[dict[str, str]] = []

    for i, date in enumerate(missing, 1):
        try:
            row = summarize_options(bhavcopy_filtered(date, "option"))
            append_history(Path("data/historical_option_features.csv"), row)
            try:
                participant_row = summarize_participant(participant_nselib(date), date)
                append_history(Path("data/historical_participant_oi.csv"), participant_row)
            except Exception as exc:  # noqa: BLE001 - option repair can still succeed; audit participant separately
                participant_failed.append({"date": date, "error": str(exc)})
                print(i, "/", len(missing), date, "PARTICIPANT_FAIL", exc, flush=True)
            repaired.append(date)
            print(i, "/", len(missing), date, "OK", flush=True)
        except Exception as exc:  # noqa: BLE001 - batch repair should continue and write audit CSV
            failed.append({"date": date, "error": str(exc)})
            print(i, "/", len(missing), date, "FAIL", exc, flush=True)

    print("REPAIRED", len(repaired), "FAILED", len(failed), "PARTICIPANT_FAILED", len(participant_failed))
    Path("reports").mkdir(exist_ok=True)
    if failed:
        pd.DataFrame(failed).to_csv("reports/history_repair_failures.csv", index=False)
    if participant_failed:
        pd.DataFrame(participant_failed).to_csv("reports/participant_repair_failures.csv", index=False)


if __name__ == "__main__":
    main()
