"""Tests for GO/NO-GO report evaluation."""

import pytest

from trading_advisor.backtest.go_nogo import (
    CriterionResult,
    GoNoGoReport,
    evaluate_go_nogo,
    format_go_nogo_report,
)

# All-passing baseline kwargs
_PASSING_KWARGS: dict[str, object] = {
    "sharpe": 1.2,
    "max_drawdown_pct": 0.10,
    "wfe": 0.65,
    "mc_5th_percentile": 16000.0,
    "starting_capital": 15000.0,
    "shuffled_p_value": 0.005,
    "t_statistic": 3.0,
    "win_rate": 0.50,
    "total_trades": 150,
}


class TestEvaluateGoNoGo:
    """Tests for evaluate_go_nogo."""

    def test_all_pass_go(self) -> None:
        """All criteria passing -> GO."""
        report = evaluate_go_nogo(**_PASSING_KWARGS)  # type: ignore[arg-type]
        assert report.verdict == "GO"
        assert all(c.passed for c in report.criteria)
        assert len(report.criteria) == 8

    def test_sharpe_fail(self) -> None:
        """Sharpe below 0.5 -> NO-GO."""
        kwargs = {**_PASSING_KWARGS, "sharpe": 0.3}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        sharpe_c = [c for c in report.criteria if c.name == "Sharpe Ratio"][0]
        assert sharpe_c.passed is False

    def test_max_drawdown_fail(self) -> None:
        """Max drawdown >= 20% -> NO-GO."""
        kwargs = {**_PASSING_KWARGS, "max_drawdown_pct": 0.25}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        dd_c = [c for c in report.criteria if c.name == "Max Drawdown"][0]
        assert dd_c.passed is False

    def test_wfe_fail(self) -> None:
        """WFE <= 50% -> NO-GO."""
        kwargs = {**_PASSING_KWARGS, "wfe": 0.30}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        wfe_c = [c for c in report.criteria if c.name == "Walk-Forward Efficiency"][0]
        assert wfe_c.passed is False

    def test_monte_carlo_fail(self) -> None:
        """MC 5th percentile <= starting capital -> NO-GO."""
        kwargs = {**_PASSING_KWARGS, "mc_5th_percentile": 14000.0}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        mc_c = [c for c in report.criteria if c.name == "Monte Carlo 5th Percentile"][0]
        assert mc_c.passed is False

    def test_shuffled_p_fail(self) -> None:
        """Shuffled p-value >= 0.01 -> NO-GO."""
        kwargs = {**_PASSING_KWARGS, "shuffled_p_value": 0.05}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        p_c = [c for c in report.criteria if c.name == "Shuffled-Price p-value"][0]
        assert p_c.passed is False

    def test_t_stat_fail(self) -> None:
        """t-stat <= 2.0 -> NO-GO."""
        kwargs = {**_PASSING_KWARGS, "t_statistic": 1.5}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        t_c = [c for c in report.criteria if c.name == "t-Statistic"][0]
        assert t_c.passed is False

    def test_win_rate_too_low(self) -> None:
        """Win rate below 35% -> NO-GO."""
        kwargs = {**_PASSING_KWARGS, "win_rate": 0.20}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        wr_c = [c for c in report.criteria if c.name == "Win Rate"][0]
        assert wr_c.passed is False

    def test_win_rate_too_high(self) -> None:
        """Win rate above 75% -> NO-GO (overfitting flag)."""
        kwargs = {**_PASSING_KWARGS, "win_rate": 0.80}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        wr_c = [c for c in report.criteria if c.name == "Win Rate"][0]
        assert wr_c.passed is False

    def test_total_trades_fail(self) -> None:
        """Total trades <= 100 -> NO-GO."""
        kwargs = {**_PASSING_KWARGS, "total_trades": 50}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        assert report.verdict == "NO-GO"
        tt_c = [c for c in report.criteria if c.name == "Total Trades"][0]
        assert tt_c.passed is False

    # -- Boundary tests --

    def test_sharpe_at_boundary(self) -> None:
        """Sharpe exactly 0.5 -> NOT passed (strict >)."""
        kwargs = {**_PASSING_KWARGS, "sharpe": 0.5}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        sharpe_c = [c for c in report.criteria if c.name == "Sharpe Ratio"][0]
        assert sharpe_c.passed is False

    def test_drawdown_at_boundary(self) -> None:
        """Max drawdown exactly 0.20 -> NOT passed (strict <)."""
        kwargs = {**_PASSING_KWARGS, "max_drawdown_pct": 0.20}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        dd_c = [c for c in report.criteria if c.name == "Max Drawdown"][0]
        assert dd_c.passed is False

    def test_win_rate_at_lower_boundary(self) -> None:
        """Win rate exactly 0.35 -> PASSED (inclusive >=)."""
        kwargs = {**_PASSING_KWARGS, "win_rate": 0.35}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        wr_c = [c for c in report.criteria if c.name == "Win Rate"][0]
        assert wr_c.passed is True

    def test_win_rate_at_upper_boundary(self) -> None:
        """Win rate exactly 0.75 -> PASSED (inclusive <=)."""
        kwargs = {**_PASSING_KWARGS, "win_rate": 0.75}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        wr_c = [c for c in report.criteria if c.name == "Win Rate"][0]
        assert wr_c.passed is True

    def test_total_trades_at_boundary(self) -> None:
        """Total trades exactly 100 -> NOT passed (strict >)."""
        kwargs = {**_PASSING_KWARGS, "total_trades": 100}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        tt_c = [c for c in report.criteria if c.name == "Total Trades"][0]
        assert tt_c.passed is False

    def test_mc_at_boundary(self) -> None:
        """MC 5th percentile exactly equal to starting capital -> NOT passed."""
        kwargs = {**_PASSING_KWARGS, "mc_5th_percentile": 15000.0}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        mc_c = [c for c in report.criteria if c.name == "Monte Carlo 5th Percentile"][0]
        assert mc_c.passed is False

    def test_shuffled_p_at_boundary(self) -> None:
        """p-value exactly 0.01 -> NOT passed (strict <)."""
        kwargs = {**_PASSING_KWARGS, "shuffled_p_value": 0.01}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        p_c = [c for c in report.criteria if c.name == "Shuffled-Price p-value"][0]
        assert p_c.passed is False


class TestFormatReport:
    """Tests for format_go_nogo_report."""

    def test_go_verdict_in_output(self) -> None:
        """GO verdict appears in formatted output."""
        report = evaluate_go_nogo(**_PASSING_KWARGS)  # type: ignore[arg-type]
        text = format_go_nogo_report(report)
        assert "GO" in text
        assert "PASS" in text

    def test_nogo_verdict_in_output(self) -> None:
        """NO-GO verdict and FAIL appear in formatted output."""
        kwargs = {**_PASSING_KWARGS, "sharpe": 0.1}
        report = evaluate_go_nogo(**kwargs)  # type: ignore[arg-type]
        text = format_go_nogo_report(report)
        assert "NO-GO" in text
        assert "FAIL" in text

    def test_all_criteria_listed(self) -> None:
        """All 8 criteria appear in the formatted output."""
        report = evaluate_go_nogo(**_PASSING_KWARGS)  # type: ignore[arg-type]
        text = format_go_nogo_report(report)
        assert "Sharpe Ratio" in text
        assert "Max Drawdown" in text
        assert "Walk-Forward Efficiency" in text
        assert "Monte Carlo" in text
        assert "Shuffled-Price" in text
        assert "t-Statistic" in text
        assert "Win Rate" in text
        assert "Total Trades" in text


class TestDataclasses:
    """Tests for dataclass properties."""

    def test_criterion_result_frozen(self) -> None:
        """CriterionResult is immutable."""
        c = CriterionResult(name="test", value=1.0, threshold="> 0", comparison=">", passed=True)
        with pytest.raises(AttributeError):
            c.passed = False  # type: ignore[misc]

    def test_go_nogo_report_frozen(self) -> None:
        """GoNoGoReport is immutable."""
        r = GoNoGoReport(criteria=(), verdict="GO")
        with pytest.raises(AttributeError):
            r.verdict = "NO-GO"  # type: ignore[misc]
