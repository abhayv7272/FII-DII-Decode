# GitHub Setup — NIFTY 9 PM Report + Daily Email

This repository is prepared to run every weekday at approximately **9:00 PM IST** using GitHub Actions and email the professional report to **abhayv7272@gmail.com**.

> GitHub scheduled workflows use UTC and may start a few minutes late during platform load. `30 15 * * 1-5` means 15:30 UTC = 21:00 IST, Monday–Friday.

## 1. Create the GitHub repository

1. Sign in to GitHub.
2. Create a new repository, preferably **Private**.
3. Do not initialize it with a README if you will push this whole folder.
4. Upload/push the **contents inside** `market prediction for github` so that `.github`, `src`, `data`, `reports`, `run_production.py`, and `requirements.txt` are at the repository root.

Using Git locally:

```bash
cd "market prediction for github"
git init
git add .
git commit -m "Initial hardened NIFTY prediction system"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

## 2. Enable GitHub Actions write access

Repository → **Settings** → **Actions** → **General** → Workflow permissions:

- Select **Read and write permissions**.
- Save.

The workflow needs write access only to preserve compact historical state and reports. Raw run snapshots are uploaded as 30-day Actions artifacts and are not committed.

## 3. Create a Gmail App Password

Do **not** use your normal Gmail password.

1. Enable 2-Step Verification on the Gmail account that will send the reports.
2. Open Google Account → Security → App passwords.
3. Create an app password named `GitHub NIFTY Report`.
4. Copy the generated 16-character app password.

If Google does not show App passwords, check that 2-Step Verification is enabled and that the account policy permits app passwords.

## 4. Add GitHub repository secrets

Repository → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

Add:

| Secret | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `465` |
| `SMTP_USERNAME` | Gmail address used to send mail |
| `SMTP_PASSWORD` | The Gmail App Password, not normal password |
| `SMTP_FROM` | Same Gmail address used in `SMTP_USERNAME` |

Recipient is already configured as:

```text
abhayv7272@gmail.com
```

Never put the App Password in code, README, chat screenshots, issues, commits, Actions logs, or downloadable artifacts.

## 5. Test manually

1. Open the repository's **Actions** tab.
2. Select **NIFTY 9 PM Prediction Report**.
3. Click **Run workflow**.
4. Keep `session_date` as `auto`.
5. Watch the steps.
6. Confirm the email arrives (also check Spam/Promotions).

The email contains the Markdown report and attaches the JSON report, latest source manifest, and ultra-hard audit.

### HTML email format (Gmail-compatible)

Since the HTML upgrade, the nightly email is sent as **multipart/alternative**:

- **text/html** — styled dashboard view (header, decision badge, color-coded gates, metric cards, key levels, weekly risk map, source-health pills, safety boxes). Rendering lives in `src/email_template.py` and uses only **inline CSS with table layout** so Gmail renders it correctly (Gmail strips `<style>` blocks and does not support flexbox/grid).
- **text/plain** — the original Markdown report, preserved verbatim as the fallback part.

Attachments (Markdown report, JSON report, source manifest, ultra-hard audit) are unchanged, and pipeline-failure runs get a dedicated red failure template whose safe decision is always **WAIT / NO TRADE**.

**Safety note:** the HTML layer is presentation-only. The decision string, gate states and probabilities are rendered verbatim from the report JSON; raw class probabilities are always labelled as class probabilities (never profit probabilities) while the research promotion gate is failed. A WAIT / NO TRADE outcome can never be rewritten into a trade instruction by the template. Tests: `tests/test_email_template.py`.

## 6. Automatic schedule

Workflow file:

```text
.github/workflows/nifty-9pm-report.yml
```

Schedule:

```yaml
- cron: "30 15 * * 1-5"
```

This runs Monday–Friday at approximately 9 PM IST. On exchange holidays, `auto` chooses the latest completed trading session. Duplicate dates are updated idempotently.

## 7. Failure behavior

- Tests run before prediction.
- If tests fail, the prediction pipeline does not run.
- If data/pipeline fails, a **PIPELINE FAILURE / WAIT / NO TRADE** email is generated.
- Critical price, options, and futures must be fresh and session-matched.
- Stale/future-dated/schema-mismatched data cannot authorize a trade.
- GitHub Actions artifacts preserve logs and run evidence for 30 days.

## 8. Source blocks on GitHub-hosted runners

NSE or other providers may sometimes block cloud/GitHub IP addresses. The system has primary adapters, alternative adapters, retry, cache, hashes, and fail-closed quality gates, but no free source can guarantee availability.

If GitHub-hosted runners are consistently blocked:

1. Use a **self-hosted GitHub Actions runner** on an Indian VPS/home machine, or
2. Use a licensed market-data API and add a new adapter, or
3. Run `scripts/run_9pm_pipeline.sh` locally with cron/Task Scheduler.

Do not weaken the freshness gates just to force a prediction.

## 9. Repository inactivity caveat

GitHub may disable scheduled workflows in inactive public repositories after an extended period. Keep the repository active and verify the Actions schedule regularly. A private repository is recommended for operational reports.

## 10. Local verification before push

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests
python run_production.py --date auto
python verify_reproducibility.py --runs 2 --date auto
```

Current hardened policy may correctly return **WAIT / NO TRADE** even when the raw class score is high, because model promotion, data quality, date, event, sample, and cost gates are independent.
