"""Orchestration functions for WealthOps jobs.

Functions:
  run_ingest    — fetch data + indicators + signal scan + notify
  run_briefing  — send daily briefing
  run_bot       — start Telegram bot (polling mode)
"""

import datetime

_STARTING_CAPITAL: float = 15000.0
_BOOTSTRAP_START: str = "2015-01-01"


def run_ingest(*, bootstrap: bool = False) -> None:
    """Full ingest pipeline: fetch -> indicators -> composite -> signal -> notify.

    Args:
        bootstrap: When ``True``, fetch full history from ``2015-01-01``.
            Defaults to ``False``.
    """
    import asyncio
    import time

    from trading_advisor.config import create_storage, load_settings
    from trading_advisor.data.fred import FredProvider
    from trading_advisor.data.ingest import DataIngestor
    from trading_advisor.data.tiingo import TiingoProvider
    from trading_advisor.guards import (
        DrawdownGate,
        EventGuard,
        MacroGate,
        PullbackZone,
        TrendGate,
        load_calendar,
    )
    from trading_advisor.indicators.composite import compute_composite
    from trading_advisor.indicators.technical import compute_all_indicators
    from trading_advisor.notifications.bot import TelegramBot
    from trading_advisor.notifications.signal_store import SignalStore
    from trading_advisor.portfolio.manager import PortfolioManager
    from trading_advisor.strategy.swing_sniper import SwingSniper

    start_time = time.monotonic()
    settings = load_settings()
    storage = create_storage(settings)

    # 1. Fetch data
    ohlcv_provider = TiingoProvider(api_key=settings.tiingo_api_key)
    macro_provider = FredProvider(api_key=settings.fred_api_key)
    ingestor = DataIngestor(ohlcv_provider, macro_provider, storage)
    today = datetime.datetime.now(tz=datetime.UTC).strftime("%Y-%m-%d")
    print(f"[ingest] Running daily ingest up to {today} ...")
    start_date = _BOOTSTRAP_START if bootstrap else None
    results = ingestor.run_daily_ingest(end_date=today, start_date=start_date, fresh=bootstrap)

    for symbol, result in results.items():
        status = "OK" if result.valid else "FAILED"
        warnings = f" ({len(result.warnings)} warnings)" if result.warnings else ""
        print(f"  {symbol}: {status}{warnings}")
        for err in result.errors:
            print(f"    ERROR: {err}")
        for warn in result.warnings:
            print(f"    WARN:  {warn}")

    # 2. Compute indicators + composite
    xau_df = storage.read_parquet("ohlcv/XAUUSD_daily")
    eurusd_df = storage.read_parquet("ohlcv/EURUSD_daily")
    indicators = compute_all_indicators(xau_df, eurusd_df)
    composite_df = compute_composite(indicators)

    # 3. Get latest composite score
    latest = composite_df.iloc[-1]
    composite_score = float(latest["composite"])
    signal_class = str(latest["signal"])

    # 4. Store market context for briefing
    storage.write_json(
        "state/market_context",
        {
            "date": today,
            "composite": composite_score,
            "signal_class": signal_class,
        },
    )

    print(f"[ingest] Composite: {composite_score:.2f}\u03c3 ({signal_class})")

    # 5. Check for signal
    evaluation_date = datetime.date.fromisoformat(today)
    portfolio_mgr = PortfolioManager(storage)
    if not storage.exists("state/portfolio"):
        portfolio_mgr.update_equity(_STARTING_CAPITAL)

    # Load economic calendar from the data directory
    calendar_path = settings.data_dir / "calendars" / "economic_calendar.json"
    calendar = load_calendar(calendar_path)
    guards = [MacroGate(), TrendGate(), EventGuard(calendar), PullbackZone(), DrawdownGate()]
    guards_enabled = settings.guards_enabled

    # EUR/USD needs SMA_200 for MacroGate
    eurusd_with_sma = eurusd_df.copy()
    eurusd_with_sma["sma_200"] = eurusd_df["close"].rolling(200).mean()

    strategy = SwingSniper(portfolio_mgr, guards, guards_enabled)
    signals = strategy.generate_signals(
        indicators=composite_df,
        eurusd=eurusd_with_sma,
        evaluation_date=evaluation_date,
    )

    # 6. Store pending signal + send card if signal fired
    signal_store = SignalStore(storage)
    hb_chat = settings.telegram_heartbeat_chat_id or settings.telegram_chat_id
    bot = TelegramBot(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        heartbeat_chat_id=hb_chat,
        storage=storage,
        portfolio_manager=portfolio_mgr,
        signal_store=signal_store,
    )

    if signals:
        from trading_advisor.strategy.signal import TradeSignal

        trade_signal: TradeSignal = signals[0]  # type: ignore[assignment]
        signal_store.save_pending(trade_signal)
    else:
        trade_signal = None  # type: ignore[assignment]
        print("[ingest] No signal today.")

    # 7. Send Telegram notifications + heartbeat (single event loop)
    duration = time.monotonic() - start_time
    timestamp = datetime.datetime.now(tz=datetime.UTC)

    async def _send_all() -> None:
        if trade_signal is not None:
            await bot.send_signal_card(trade_signal)
        await bot.send_heartbeat(
            command="ingest",
            timestamp=timestamp,
            duration_s=duration,
            composite=composite_score,
            signal_class=signal_class,
        )

    asyncio.run(_send_all())

    if trade_signal is not None:
        print(f"[ingest] Signal: {trade_signal.signal_strength} -- sent to Telegram")

    storage.write_json(
        "state/heartbeat",
        {"command": "ingest", "timestamp": timestamp.isoformat()},
    )

    print("[ingest] Done.")


def run_briefing() -> None:
    """Daily briefing: portfolio + market -> Telegram -> heartbeat."""
    import asyncio
    import time

    from trading_advisor.config import create_storage, load_settings
    from trading_advisor.notifications.bot import TelegramBot
    from trading_advisor.notifications.formatters import BriefingData
    from trading_advisor.notifications.signal_store import SignalStore
    from trading_advisor.portfolio.manager import PortfolioManager

    start_time = time.monotonic()
    settings = load_settings()
    storage = create_storage(settings)
    portfolio_mgr = PortfolioManager(storage)
    if not storage.exists("state/portfolio"):
        portfolio_mgr.update_equity(_STARTING_CAPITAL)
    state = portfolio_mgr.state
    signal_store = SignalStore(storage)

    # Read market context (written by ingest)
    composite_score = 0.0
    signal_class = "NEUTRAL"
    if storage.exists("state/market_context"):
        market_ctx = storage.read_json("state/market_context")
        composite_score = float(str(market_ctx.get("composite", 0.0)))
        signal_class = str(market_ctx.get("signal_class", "NEUTRAL"))

    # Read latest XAU/USD price for unrealized P&L
    current_prices: dict[str, float] = {}
    if storage.exists("ohlcv/XAUUSD_daily"):
        xau_df = storage.read_parquet("ohlcv/XAUUSD_daily")
        current_prices["XAU/USD"] = float(xau_df.iloc[-1]["close"])

    # Compute equity = cash + unrealized
    equity = state.cash + sum(
        p.size * current_prices.get(p.symbol, p.entry_price) for p in state.positions
    )

    data = BriefingData(
        date=datetime.date.today(),
        portfolio_state=state,
        equity=equity,
        starting_capital=_STARTING_CAPITAL,
        current_prices=current_prices,
        composite_score=composite_score,
        signal_class=signal_class,
        pending_signal=signal_store.load_pending(),
    )

    hb_chat = settings.telegram_heartbeat_chat_id or settings.telegram_chat_id
    bot = TelegramBot(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        heartbeat_chat_id=hb_chat,
        storage=storage,
        portfolio_manager=portfolio_mgr,
        signal_store=signal_store,
    )

    # Send briefing + heartbeat (single event loop)
    duration = time.monotonic() - start_time
    timestamp = datetime.datetime.now(tz=datetime.UTC)

    async def _send_all() -> None:
        await bot.send_briefing(data)
        await bot.send_heartbeat(
            command="briefing",
            timestamp=timestamp,
            duration_s=duration,
            composite=composite_score,
            signal_class=signal_class,
        )

    asyncio.run(_send_all())

    storage.write_json(
        "state/heartbeat",
        {"command": "briefing", "timestamp": timestamp.isoformat()},
    )

    print("[briefing] Done.")


def run_bot() -> None:
    """Start the Telegram bot in polling mode."""
    from trading_advisor.config import create_storage, load_settings
    from trading_advisor.notifications.bot import TelegramBot
    from trading_advisor.notifications.signal_store import SignalStore
    from trading_advisor.portfolio.manager import PortfolioManager

    settings = load_settings()
    storage = create_storage(settings)
    portfolio_mgr = PortfolioManager(storage)
    if not storage.exists("state/portfolio"):
        portfolio_mgr.update_equity(_STARTING_CAPITAL)
    signal_store = SignalStore(storage)
    hb_chat = settings.telegram_heartbeat_chat_id or settings.telegram_chat_id
    bot = TelegramBot(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        heartbeat_chat_id=hb_chat,
        storage=storage,
        portfolio_manager=portfolio_mgr,
        signal_store=signal_store,
    )
    print("[bot] Starting Telegram bot in polling mode ...")
    bot.start_polling()


def run_backtest_report(*, output_path: str = "backtest_report.html") -> None:
    """Run the full backtest and write an HTML report.

    Args:
        output_path: File path for the HTML report output.
    """
    from trading_advisor.backtest import run_backtest
    from trading_advisor.backtest.report import compute_metrics, generate_report
    from trading_advisor.config import create_storage, load_settings
    from trading_advisor.guards import (
        DrawdownGate,
        EventGuard,
        MacroGate,
        PullbackZone,
        TrendGate,
        load_calendar,
    )
    from trading_advisor.indicators.composite import compute_composite
    from trading_advisor.indicators.technical import compute_all_indicators

    settings = load_settings()
    storage = create_storage(settings)

    # Read data from storage
    xau_df = storage.read_parquet("ohlcv/XAUUSD_daily")
    eurusd_df = storage.read_parquet("ohlcv/EURUSD_daily")
    fedfunds_df = storage.read_parquet("macro/FEDFUNDS")
    fedfunds_series = fedfunds_df["value"]

    # Compute indicators + composite
    indicators = compute_all_indicators(xau_df, eurusd_df)
    composite_df = compute_composite(indicators)

    # EUR/USD needs SMA_200 for MacroGate
    eurusd_with_sma = eurusd_df.copy()
    eurusd_with_sma["sma_200"] = eurusd_df["close"].rolling(200).mean()

    # Set up guards
    calendar_path = settings.data_dir / "calendars" / "economic_calendar.json"
    calendar = load_calendar(calendar_path)
    guards = [MacroGate(), TrendGate(), EventGuard(calendar), PullbackZone(), DrawdownGate()]

    # Run backtest
    result = run_backtest(
        indicators=composite_df,
        eurusd=eurusd_with_sma,
        guards=guards,
        guards_enabled=settings.guards_enabled,
        fedfunds=fedfunds_series,
        starting_capital=_STARTING_CAPITAL,
    )

    # Compute metrics + generate report
    metrics = compute_metrics(result, fedfunds_series)
    html = generate_report(result, metrics)

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(html)

    # Print summary
    print(f"[backtest] Report written to {output_path}")
    print(f"  Total trades: {metrics.get('total_trades', 0):.0f}")
    print(f"  Sharpe ratio: {metrics.get('sharpe', 0):.2f}")
    print(f"  Max drawdown: {metrics.get('max_drawdown_pct', 0):.1f}%")
    print(f"  Profit factor: {metrics.get('profit_factor', 0):.2f}")
    print(f"  Win rate: {metrics.get('win_rate', 0):.1%}")
