# Request and Build Timeline

This is a structured reconstruction of the conversation requirements and outcomes, not a verbatim transcript export.

1. Build an advanced next-day and Monday–Friday market predictor in VS Code, aiming for high accuracy.
2. Use the supplied FII/DII/Pro/Client, options, VIX, pre-open, sweep/trap and V10 design.
3. Create a Streamlit dashboard and run a preview server.
4. Measure accuracy honestly and reject an unproven 80% claim.
5. Improve the price-only model, add selective WAIT behavior and compare binary/three-class outputs.
6. Add participant OI, cash, VIX, option-chain, sector, heavyweight and global context.
7. Add psychology/manipulation proxies, trap/sweep logic and ranked levels.
8. Add broad technical indicators, then reject the overfit all-indicator model when it performed worse.
9. Add gap/intraday targets, regime models, meta-label filters, costs and event gates.
10. Fetch two years of EOD options/futures history and participant OI; build a derivatives specialist.
11. Build a resilient multi-source 9 PM pipeline with retries, fallbacks, cache, provenance and professional reports.
12. Connect the pipeline to next-day and weekly decision reporting, including long/short/swing/investment context.
13. Verify deterministic reproducibility.
14. Perform an ultra-hard bug audit.
15. Repair 37 omitted sessions, target leakage/label errors, fallback schemas, unit mismatches, pivots, cache safety, atomicity, model promotion and report gates.
16. Revoke the optimistic derivative result after corrected data showed weak, negative-after-cost performance.
17. Package everything for GitHub Actions with a weekday 9 PM IST schedule and daily email to `abhayv7272@gmail.com`.

The current authoritative state is documented in `docs/CHAT_HANDOFF.md` and `reports/ultra_hard_audit.md`.
