"""GO/NO-GO report: evaluates kill conditions and produces a verdict.

Criteria (from phase1-plan.md):
  - Sharpe > 0.5
  - Max drawdown < 20%
  - Walk-forward efficiency > 50%
  - Monte Carlo 5th percentile > starting capital
  - Shuffled-price p-value < 0.01
  - t-statistic > 2.0
  - Win rate between 35% and 75%
  - Total trades > 100
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CriterionResult:
    """Result of evaluating a single GO/NO-GO criterion.

    Attributes:
        name: Human-readable criterion name.
        value: The actual measured value.
        threshold: The threshold for passing.
        comparison: How the value is compared to threshold (e.g. ">", "<", "range").
        passed: Whether this criterion passed.
    """

    name: str
    value: float
    threshold: str
    comparison: str
    passed: bool


@dataclass(frozen=True)
class GoNoGoReport:
    """Complete GO/NO-GO evaluation report.

    Attributes:
        criteria: Tuple of individual criterion results.
        verdict: "GO" if all criteria pass, "NO-GO" otherwise.
    """

    criteria: tuple[CriterionResult, ...]
    verdict: str


def evaluate_go_nogo(
    sharpe: float,
    max_drawdown_pct: float,
    wfe: float,
    mc_5th_percentile: float,
    starting_capital: float,
    shuffled_p_value: float,
    t_statistic: float,
    win_rate: float,
    total_trades: int,
) -> GoNoGoReport:
    """Evaluate all GO/NO-GO criteria and produce a verdict.

    Args:
        sharpe: Annualized Sharpe ratio from backtest.
        max_drawdown_pct: Maximum drawdown as a fraction (e.g. 0.15 for 15%).
        wfe: Walk-forward efficiency as a fraction (e.g. 0.6 for 60%).
        mc_5th_percentile: 5th percentile terminal equity from Monte Carlo.
        starting_capital: Starting capital for Monte Carlo comparison.
        shuffled_p_value: p-value from shuffled-price test.
        t_statistic: t-statistic of trade returns.
        win_rate: Win rate as a fraction (e.g. 0.45 for 45%).
        total_trades: Total number of trades.

    Returns:
        GoNoGoReport with per-criterion results and overall verdict.
    """
    criteria: list[CriterionResult] = []

    # 1. Sharpe > 0.5
    criteria.append(
        CriterionResult(
            name="Sharpe Ratio",
            value=sharpe,
            threshold="> 0.5",
            comparison=">",
            passed=sharpe > 0.5,
        )
    )

    # 2. Max drawdown < 20%
    criteria.append(
        CriterionResult(
            name="Max Drawdown",
            value=max_drawdown_pct,
            threshold="< 0.20",
            comparison="<",
            passed=max_drawdown_pct < 0.20,
        )
    )

    # 3. WFE > 50%
    criteria.append(
        CriterionResult(
            name="Walk-Forward Efficiency",
            value=wfe,
            threshold="> 0.50",
            comparison=">",
            passed=wfe > 0.50,
        )
    )

    # 4. Monte Carlo 5th percentile > starting capital
    criteria.append(
        CriterionResult(
            name="Monte Carlo 5th Percentile",
            value=mc_5th_percentile,
            threshold=f"> {starting_capital:.0f}",
            comparison=">",
            passed=mc_5th_percentile > starting_capital,
        )
    )

    # 5. Shuffled-price p < 0.01
    criteria.append(
        CriterionResult(
            name="Shuffled-Price p-value",
            value=shuffled_p_value,
            threshold="< 0.01",
            comparison="<",
            passed=shuffled_p_value < 0.01,
        )
    )

    # 6. t-stat > 2.0
    criteria.append(
        CriterionResult(
            name="t-Statistic",
            value=t_statistic,
            threshold="> 2.0",
            comparison=">",
            passed=t_statistic > 2.0,
        )
    )

    # 7. Win rate between 35% and 75%
    criteria.append(
        CriterionResult(
            name="Win Rate",
            value=win_rate,
            threshold="0.35 - 0.75",
            comparison="range",
            passed=0.35 <= win_rate <= 0.75,
        )
    )

    # 8. Total trades > 100
    criteria.append(
        CriterionResult(
            name="Total Trades",
            value=float(total_trades),
            threshold="> 100",
            comparison=">",
            passed=total_trades > 100,
        )
    )

    verdict = "GO" if all(c.passed for c in criteria) else "NO-GO"

    return GoNoGoReport(criteria=tuple(criteria), verdict=verdict)


def format_go_nogo_report(report: GoNoGoReport) -> str:
    """Format a GO/NO-GO report as a human-readable text string.

    Args:
        report: The GoNoGoReport to format.

    Returns:
        Multi-line formatted string.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(f"  GO/NO-GO VERDICT: {report.verdict}")
    lines.append("=" * 60)
    lines.append("")

    for c in report.criteria:
        status = "PASS" if c.passed else "FAIL"
        lines.append(f"  [{status}] {c.name}: {c.value:.4f} ({c.threshold})")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
