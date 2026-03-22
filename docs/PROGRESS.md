# WealthOps — Progress Tracker


---

## Recent Activity

_Update this section after each work session. Keep the last 5-10 entries. Oldest entries can be archived or deleted._

| Date | What Happened |
|------|--------------|
| 2026-03-22 | Refined Claude Code workflow: merged /build and /auto-build, trimmed coding-standards.md, added plans/ log directory, fixed permissions, added src/ rule, improved agent prompts, trimmed PROGRESS.md. |
| 2026-03-17 | Created CLAUDE.md routing document. Refined memory bank architecture: CLAUDE.md as entry point, phase1-plan.md trimmed to strategy-only, PROGRESS.md expanded with decisions log. Planning to use Notion for granular task tracking. |
| 2026-03-10 | Initial project planning complete. All four docs (phase1-plan, Architecture, CODING_STANDARDS, PROGRESS) drafted and reviewed. |

---

## Decisions Made

_Log significant decisions here with brief rationale so they don't get re-discussed._

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-22 | Plans as logs in docs/plans/ (gitignored) | Avoids re-planning, creates audit trail, user deletes manually. |
| 2026-03-22 | Reviewer uses sonnet, scoped to changed files only | Opus overkill for this project size. Scoping saves tokens. |
| 2026-03-22 | No PostToolUse test hook | Running tests mid-TDD creates noise — tests should fail while writing code. Checkpoint verification is the right pattern. |
| 2026-03-10 | EUR/USD as inverted DXY proxy | Same Tiingo forex endpoint as gold. No extra data source needed. |
| 2026-03-10 | Guard toggle system with ablation study | GUARDS_ENABLED config dict. Data decides which guards stay, not assumptions. |
| 2026-03-10 | StorageBackend ABC with LocalStorage + S3Storage | Deployment-agnostic from day one. S3 behind optional `[aws]` extra. |
| 2026-03-10 | €15,000 starting capital | Comfortable headroom above IG minimums at 2% risk per trade. |
| 2026-03-10 | No vectorbt | Trap Order logic too custom. Write backtest loop with pandas. |
| 2026-03-10 | All config via WEALTHOPS_* env vars | No config files. python-dotenv for local, SSM/Lambda env for AWS. |

---

## Open Questions

_Things still being figured out. Remove once resolved and add to Decisions Made._

- **pandas-ta vs manual indicator implementation?** pandas-ta is convenient but may not match TradingView exactly for some indicators. Need to verify during Task 1B.
- **Click vs Typer for CLI?** Both work. Typer is newer and has auto-generated help. Pick during Task 1H.
- **Support/Resistance detection method?** "Price clustering" is vague. Need to define the exact algorithm during Task 1B. Options: pivot points, volume profile zones (no volume for gold though), or simple rolling min/max proximity.

---

## Kill Conditions (stop and reassess if any trigger)
- Backtest Sharpe < 0.3 after tuning
- Shuffled-price test passes (p > 0.05)
- Walk-forward efficiency < 30%
- Win rate > 75% (overfit)
- < 50 trades in 5 years

_For detailed task checklist, see `docs/strategy/phase1-plan.md`._
