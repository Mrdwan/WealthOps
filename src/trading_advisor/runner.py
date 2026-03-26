"""Entry points for the WealthOps runner.

Commands:
  wealthops ingest    — fetch data + indicators + signal scan + notify
  wealthops briefing  — send daily briefing
  wealthops bot       — start Telegram bot (polling mode)
"""

import datetime
import sys


def _run_ingest() -> None:
    """Full ingest pipeline: fetch -> indicators -> composite -> signal -> notify."""
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
    results = ingestor.run_daily_ingest(end_date=today)

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

    # Load economic calendar from the data directory
    calendar_path = settings.data_dir / "calendars" / "economic_calendar.json"
    calendar = load_calendar(calendar_path)
    guards = [MacroGate(), TrendGate(), EventGuard(calendar), PullbackZone(), DrawdownGate()]
    guards_enabled: dict[str, bool] = {}  # all enabled by default

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
        asyncio.run(bot.send_signal_card(trade_signal))
        print(f"[ingest] Signal: {trade_signal.signal_strength} -- sent to Telegram")
    else:
        print("[ingest] No signal today.")

    # 7. Send heartbeat
    duration = time.monotonic() - start_time
    timestamp = datetime.datetime.now(tz=datetime.UTC)
    asyncio.run(
        bot.send_heartbeat(
            command="ingest",
            timestamp=timestamp,
            duration_s=duration,
            composite=composite_score,
            signal_class=signal_class,
        )
    )

    print("[ingest] Done.")


def _run_briefing() -> None:
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
        starting_capital=15000.0,
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

    asyncio.run(bot.send_briefing(data))

    # Heartbeat
    duration = time.monotonic() - start_time
    timestamp = datetime.datetime.now(tz=datetime.UTC)
    asyncio.run(
        bot.send_heartbeat(
            command="briefing",
            timestamp=timestamp,
            duration_s=duration,
            composite=composite_score,
            signal_class=signal_class,
        )
    )

    print("[briefing] Done.")


def _run_bot() -> None:
    """Start the Telegram bot in polling mode."""
    from trading_advisor.config import create_storage, load_settings
    from trading_advisor.notifications.bot import TelegramBot
    from trading_advisor.notifications.signal_store import SignalStore
    from trading_advisor.portfolio.manager import PortfolioManager

    settings = load_settings()
    storage = create_storage(settings)
    portfolio_mgr = PortfolioManager(storage)
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


def main() -> None:
    """CLI entry point dispatched by pyproject.toml [project.scripts]."""
    commands = ("ingest", "briefing", "bot")
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: wealthops [{' | '.join(commands)}]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "ingest":
        _run_ingest()
    elif command == "briefing":
        _run_briefing()
    elif command == "bot":
        _run_bot()


if __name__ == "__main__":
    main()
