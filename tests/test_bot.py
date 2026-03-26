"""Tests for the Telegram bot: polling, webhook, and proactive sending."""

import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from trading_advisor.notifications.bot import TelegramBot
from trading_advisor.notifications.formatters import BriefingData
from trading_advisor.notifications.signal_store import SignalStore
from trading_advisor.portfolio.manager import (
    PortfolioManager,
    PortfolioState,
    ThrottleState,
)
from trading_advisor.storage.local import LocalStorage
from trading_advisor.strategy.signal import TradeSignal


def _make_signal() -> TradeSignal:
    return TradeSignal(
        date=datetime.date(2026, 3, 10),
        asset="XAU/USD",
        direction="LONG",
        composite_score=1.65,
        signal_strength="BUY",
        trap_order_stop=2352.40,
        trap_order_limit=2353.85,
        stop_loss=2310.00,
        take_profit=2410.00,
        trailing_stop_atr_mult=2.0,
        position_size=0.05,
        risk_amount=212.00,
        risk_reward_ratio=2.72,
        guards_passed=("MacroGate", "TrendGate"),
        ttl=1,
    )


@pytest.fixture()
def bot_setup(
    tmp_path: Path,
) -> tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore]:
    """Create a TelegramBot with real local storage for testing."""
    storage = LocalStorage(tmp_path)
    manager = PortfolioManager(storage)
    manager.update_equity(15000.0)
    signal_store = SignalStore(storage)
    bot = TelegramBot(
        token="test-token",
        chat_id="12345",
        heartbeat_chat_id="67890",
        storage=storage,
        portfolio_manager=manager,
        signal_store=signal_store,
    )
    return bot, storage, manager, signal_store


def _mock_bot_send(bot: TelegramBot) -> AsyncMock:
    """Replace bot._bot with a MagicMock and return the send_message mock.

    The telegram Bot object freezes attributes, so we replace the entire
    internal _bot with a MagicMock that has an async send_message.
    """
    mock_internal_bot = MagicMock()
    mock_internal_bot.send_message = AsyncMock()
    bot._bot = mock_internal_bot  # type: ignore[assignment]
    return mock_internal_bot.send_message


# ------------------------------------------------------------------
# Proactive sending
# ------------------------------------------------------------------


async def test_send_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """send_message sends to the default chat_id."""
    bot, _, _, _ = bot_setup
    mock_send = _mock_bot_send(bot)
    await bot.send_message("hello")
    mock_send.assert_called_once_with(chat_id="12345", text="hello")


async def test_send_message_custom_chat(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """send_message with explicit chat_id overrides the default."""
    bot, _, _, _ = bot_setup
    mock_send = _mock_bot_send(bot)
    await bot.send_message("hello", chat_id="99999")
    mock_send.assert_called_once_with(chat_id="99999", text="hello")


async def test_send_signal_card(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """send_signal_card formats the signal and sends to the main chat."""
    bot, _, _, _ = bot_setup
    signal = _make_signal()
    mock_send = _mock_bot_send(bot)
    await bot.send_signal_card(signal)
    mock_send.assert_called_once()
    text = mock_send.call_args[1]["text"]
    assert "BUY Signal" in text
    assert "XAU/USD" in text


async def test_send_heartbeat(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """send_heartbeat sends to the heartbeat chat_id."""
    bot, _, _, _ = bot_setup
    mock_send = _mock_bot_send(bot)
    await bot.send_heartbeat(
        command="ingest",
        timestamp=datetime.datetime(2026, 3, 10, 23, 0, tzinfo=datetime.UTC),
        duration_s=0.4,
        composite=1.2,
        signal_class="NEUTRAL",
    )
    mock_send.assert_called_once()
    assert mock_send.call_args[1]["chat_id"] == "67890"
    assert "ingest" in mock_send.call_args[1]["text"]


async def test_send_briefing(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """send_briefing formats the data and sends to the main chat."""
    bot, _, _, _ = bot_setup
    data = BriefingData(
        date=datetime.date(2026, 3, 10),
        portfolio_state=PortfolioState(
            cash=15000.0,
            positions=(),
            high_water_mark=15000.0,
            throttle_state=ThrottleState.NORMAL,
        ),
        equity=15000.0,
        starting_capital=15000.0,
        current_prices={},
        composite_score=1.2,
        signal_class="NEUTRAL",
        pending_signal=None,
    )
    mock_send = _mock_bot_send(bot)
    await bot.send_briefing(data)
    mock_send.assert_called_once()
    assert "Daily Briefing" in mock_send.call_args[1]["text"]


# ------------------------------------------------------------------
# Authorization
# ------------------------------------------------------------------


async def test_authorized_correct_chat(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """_authorized returns True for the configured chat_id."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    assert bot._authorized(update) is True


async def test_authorized_wrong_chat(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """_authorized returns False for an unauthorized chat_id."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    assert bot._authorized(update) is False


async def test_authorized_no_chat(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """_authorized returns False when effective_chat is None."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat = None
    assert bot._authorized(update) is False


# ------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------


async def test_handle_help(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/help lists all available commands."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []

    await bot._handle_help(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "/help" in text
    assert "/status" in text


async def test_handle_unauthorized(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Unauthorized chat_id is silently ignored."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_status(update, context)

    update.message.reply_text.assert_not_called()


async def test_handle_executed_no_args(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/executed with no args returns usage message."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []

    await bot._handle_executed(update, context)

    update.message.reply_text.assert_called_once()
    assert "Usage" in update.message.reply_text.call_args[0][0]


async def test_handle_executed_invalid_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/executed with non-numeric price returns error."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["2026-03-10", "not-a-number"]

    await bot._handle_executed(update, context)

    update.message.reply_text.assert_called_once()
    assert "Invalid price" in update.message.reply_text.call_args[0][0]


async def test_handle_close_no_args(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close with no args returns usage message."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []

    await bot._handle_close(update, context)

    update.message.reply_text.assert_called_once()
    assert "Usage" in update.message.reply_text.call_args[0][0]


async def test_handle_close_invalid_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close with non-numeric price returns error."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["XAUUSD", "not-a-number"]

    await bot._handle_close(update, context)

    assert "Invalid price" in update.message.reply_text.call_args[0][0]


async def test_handle_skip_no_args(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/skip with no args returns usage message."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = []

    await bot._handle_skip(update, context)

    assert "Usage" in update.message.reply_text.call_args[0][0]


def test_start_polling(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """start_polling calls app.run_polling."""
    bot, _, _, _ = bot_setup
    with patch("trading_advisor.notifications.bot.Application") as mock_app_cls:
        mock_app = MagicMock()
        mock_app_cls.builder.return_value.token.return_value.build.return_value = mock_app
        bot.start_polling()
        mock_app.run_polling.assert_called_once()


async def test_process_webhook_update(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """process_webhook_update processes an update via the Application."""
    bot, _, _, _ = bot_setup
    with patch("trading_advisor.notifications.bot.Application") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.__aenter__ = AsyncMock(return_value=mock_app)
        mock_app.__aexit__ = AsyncMock(return_value=False)
        mock_app.process_update = AsyncMock()
        mock_app.bot = MagicMock()
        mock_app_cls.builder.return_value.token.return_value.build.return_value = mock_app

        with patch("trading_advisor.notifications.bot.Update") as mock_update_cls:
            mock_update = MagicMock()
            mock_update_cls.de_json.return_value = mock_update

            await bot.process_webhook_update({"update_id": 1})

            mock_update_cls.de_json.assert_called_once()
            mock_app.process_update.assert_called_once_with(mock_update)


async def test_handle_executed_default_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/executed with date only uses trap_order_stop from the pending signal."""
    bot, _, _, signal_store = bot_setup
    signal = _make_signal()
    signal_store.save_pending(signal)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["2026-03-10"]

    await bot._handle_executed(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "Executed" in text
    assert "2352.40" in text


async def test_handle_executed_no_signal_no_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/executed with date but no price and no pending signal returns error."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["2026-03-10"]

    await bot._handle_executed(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "No pending signal" in text


async def test_handle_close_no_price_no_data(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close without price and no stored OHLCV data asks for price."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["XAUUSD"]

    await bot._handle_close(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "Price required" in text


async def test_handle_status(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/status returns equity, P&L, drawdown, and throttle info."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_status(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Status" in text


async def test_handle_status_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Handler tolerates update.message being None."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()

    await bot._handle_status(update, context)


def test_build_application(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """_build_application registers all 8 command handlers."""
    bot, _, _, _ = bot_setup
    app = bot._build_application()
    handler_names: set[str] = set()
    for group in app.handlers.values():
        for handler in group:
            if hasattr(handler, "commands"):
                handler_names.update(handler.commands)
    expected = {"status", "portfolio", "executed", "skip", "close", "risk", "resume", "help"}
    assert handler_names == expected


async def test_process_webhook_update_none(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """process_webhook_update handles de_json returning None gracefully."""
    bot, _, _, _ = bot_setup
    with patch("trading_advisor.notifications.bot.Application") as mock_app_cls:
        mock_app = MagicMock()
        mock_app.__aenter__ = AsyncMock(return_value=mock_app)
        mock_app.__aexit__ = AsyncMock(return_value=False)
        mock_app.process_update = AsyncMock()
        mock_app.bot = MagicMock()
        mock_app_cls.builder.return_value.token.return_value.build.return_value = mock_app

        with patch("trading_advisor.notifications.bot.Update") as mock_update_cls:
            mock_update_cls.de_json.return_value = None

            await bot.process_webhook_update({"update_id": 1})

            mock_app.process_update.assert_not_called()


async def test_handle_risk(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/risk delegates to handle_risk and replies."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_risk(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Risk Dashboard" in text


async def test_handle_resume(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/resume delegates to handle_resume and replies."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_resume(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    # Not HALTED, so it should say "Not in HALTED state"
    assert "Not in HALTED" in text


async def test_handle_portfolio_no_data(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/portfolio with no stored OHLCV data still works."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_portfolio(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Portfolio" in text


async def test_handle_portfolio_with_data(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/portfolio reads the latest XAU/USD close price from storage."""
    bot, storage, _, _ = bot_setup

    import pandas as pd

    df = pd.DataFrame({"close": [2350.0, 2360.0]})
    storage.write_parquet("ohlcv/XAUUSD_daily", df)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_portfolio(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Portfolio" in text


async def test_handle_close_with_stored_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close XAUUSD without price falls back to stored close."""
    bot, storage, manager, _ = bot_setup

    import pandas as pd

    df = pd.DataFrame({"close": [2350.0, 2360.0]})
    storage.write_parquet("ohlcv/XAUUSD_daily", df)

    from trading_advisor.portfolio.manager import Position

    pos = Position(
        symbol="XAU/USD",
        entry_price=2340.0,
        size=0.05,
        entry_date=datetime.date(2026, 3, 8),
        stop_loss=2300.0,
        take_profit=2400.0,
        signal_atr=20.0,
    )
    manager.open_position(pos)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["XAUUSD"]

    await bot._handle_close(update, context)

    update.message.reply_text.assert_called_once()
    text = update.message.reply_text.call_args[0][0]
    assert "Closed" in text


async def test_handle_executed_with_explicit_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/executed with date and explicit price uses that price."""
    bot, _, _, signal_store = bot_setup
    signal = _make_signal()
    signal_store.save_pending(signal)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["2026-03-10", "2355.00"]

    await bot._handle_executed(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "Executed" in text
    assert "2355.00" in text


async def test_handle_skip_delegates(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/skip with a date delegates to handle_skip."""
    bot, _, _, signal_store = bot_setup
    signal = _make_signal()
    signal_store.save_pending(signal)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["2026-03-10"]

    await bot._handle_skip(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "skipped" in text.lower()


async def test_handle_close_with_explicit_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close with symbol and explicit price closes the position."""
    bot, _, manager, _ = bot_setup

    from trading_advisor.portfolio.manager import Position

    pos = Position(
        symbol="XAU/USD",
        entry_price=2340.0,
        size=0.05,
        entry_date=datetime.date(2026, 3, 8),
        stop_loss=2300.0,
        take_profit=2400.0,
        signal_atr=20.0,
    )
    manager.open_position(pos)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["XAUUSD", "2370.00"]

    await bot._handle_close(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "Closed" in text


async def test_handle_portfolio_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/portfolio tolerates update.message being None."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()

    await bot._handle_portfolio(update, context)


async def test_handle_executed_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/executed tolerates update.message being None (no args path)."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = []

    await bot._handle_executed(update, context)


async def test_handle_skip_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/skip tolerates update.message being None (no args path)."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = []

    await bot._handle_skip(update, context)


async def test_handle_close_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close tolerates update.message being None (no args path)."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = []

    await bot._handle_close(update, context)


async def test_handle_risk_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/risk tolerates update.message being None."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()

    await bot._handle_risk(update, context)


async def test_handle_resume_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/resume tolerates update.message being None."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()

    await bot._handle_resume(update, context)


async def test_handle_help_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/help tolerates update.message being None."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()

    await bot._handle_help(update, context)


async def test_handle_executed_no_message_with_invalid_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/executed with invalid price tolerates update.message being None."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = ["2026-03-10", "bad"]

    await bot._handle_executed(update, context)


async def test_handle_executed_no_message_no_signal(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/executed with date, no price, no pending signal, and no message."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = ["2026-03-10"]

    await bot._handle_executed(update, context)


async def test_handle_close_no_message_invalid_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close with invalid price tolerates update.message being None."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = ["XAUUSD", "bad"]

    await bot._handle_close(update, context)


async def test_handle_close_no_message_no_price_no_data(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close symbol without price/data, no message."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = ["XAUUSD"]

    await bot._handle_close(update, context)


async def test_handle_close_non_xauusd_no_price(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """/close for a non-XAUUSD symbol without price asks for price."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["EURUSD"]

    await bot._handle_close(update, context)

    text = update.message.reply_text.call_args[0][0]
    assert "Price required" in text


# ------------------------------------------------------------------
# Unauthorized access on every handler
# ------------------------------------------------------------------


async def test_handle_portfolio_unauthorized(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Unauthorized /portfolio is silently ignored."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_portfolio(update, context)

    update.message.reply_text.assert_not_called()


async def test_handle_executed_unauthorized(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Unauthorized /executed is silently ignored."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["2026-03-10"]

    await bot._handle_executed(update, context)

    update.message.reply_text.assert_not_called()


async def test_handle_skip_unauthorized(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Unauthorized /skip is silently ignored."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["2026-03-10"]

    await bot._handle_skip(update, context)

    update.message.reply_text.assert_not_called()


async def test_handle_close_unauthorized(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Unauthorized /close is silently ignored."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = ["XAUUSD", "2350"]

    await bot._handle_close(update, context)

    update.message.reply_text.assert_not_called()


async def test_handle_risk_unauthorized(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Unauthorized /risk is silently ignored."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_risk(update, context)

    update.message.reply_text.assert_not_called()


async def test_handle_resume_unauthorized(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Unauthorized /resume is silently ignored."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_resume(update, context)

    update.message.reply_text.assert_not_called()


async def test_handle_help_unauthorized(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Unauthorized /help is silently ignored."""
    bot, _, _, _ = bot_setup
    update = MagicMock()
    update.effective_chat.id = 99999
    update.message.reply_text = AsyncMock()
    context = MagicMock()

    await bot._handle_help(update, context)

    update.message.reply_text.assert_not_called()


# ------------------------------------------------------------------
# Successful execution with no message (edit scenarios)
# ------------------------------------------------------------------


async def test_handle_executed_success_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Successful /executed with no update.message does not raise."""
    bot, _, _, signal_store = bot_setup
    signal = _make_signal()
    signal_store.save_pending(signal)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = ["2026-03-10", "2352.40"]

    await bot._handle_executed(update, context)


async def test_handle_skip_success_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Successful /skip with no update.message does not raise."""
    bot, _, _, signal_store = bot_setup
    signal = _make_signal()
    signal_store.save_pending(signal)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = ["2026-03-10"]

    await bot._handle_skip(update, context)


async def test_handle_close_success_no_message(
    bot_setup: tuple[TelegramBot, LocalStorage, PortfolioManager, SignalStore],
) -> None:
    """Successful /close with no update.message does not raise."""
    bot, _, manager, _ = bot_setup

    from trading_advisor.portfolio.manager import Position

    pos = Position(
        symbol="XAU/USD",
        entry_price=2340.0,
        size=0.05,
        entry_date=datetime.date(2026, 3, 8),
        stop_loss=2300.0,
        take_profit=2400.0,
        signal_atr=20.0,
    )
    manager.open_position(pos)

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message = None
    context = MagicMock()
    context.args = ["XAUUSD", "2370.00"]

    await bot._handle_close(update, context)
