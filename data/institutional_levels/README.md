# Exact institutional levels input

The repository cannot derive the proprietary institutional-level formula from the PDFs. For live/forward testing, exact levels must be supplied externally and date-stamped.

Recommended file name:

```text
data/institutional_levels/YYYY-MM-DD.json
```

Minimal format:

```json
{
  "signal_date": "2026-09-18",
  "source": "manual/external institutional level note",
  "levels": [
    {"strike": 23270, "kind": "support", "label": "external institutional support"},
    {"strike": 23441, "kind": "resistance", "label": "external institutional resistance"}
  ]
}
```

Rules:

- `signal_date` is the evening/source date whose levels are known before the target session.
- `kind` should be `support`, `resistance`, or omitted only when role must be inferred from spot.
- Do not mix future/after-the-fact levels into a past signal date.
- Keep the original source note/provenance in `source` or each row's `label`.

The daily CLI can already consume a levels JSON via:

```bash
PYTHONPATH=src .venv/bin/python -m fiidii.cli run \
  --institutional-levels data/institutional_levels/YYYY-MM-DD.json \
  --no-email
```

V7 research consumes the historical CSV seed at `historical/institutional_levels_pdf_2026.csv` and should be extended only by untouched forward rows.
