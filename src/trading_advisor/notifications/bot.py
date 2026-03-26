"""Telegram bot: polling mode, webhook mode, and proactive message sending.

Uses python-telegram-bot v22+ (fully async).
"""

from __future__ import annotations

import datetime
from typing import Any

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from trading_advisor.notifications.commands import (
    handle_close,
    handle_executed,
    handle_help,
    handle_portfolio,
    handle_resume,
    handle_risk,
    handle_skip,
    handle_status,
)
from trading_advisor.notifications.formatters import (
    BriefingData,
    format_daily_briefing,
    format_heartbeat,
    format_signal_card,
)
from trading_advisor.notifications.signal_store import SignalStore
from trading_advisor.portfolio.manager import PortfolioManager
from trading_advisor.storage.base import StorageBackend
from trading_advisor.strategy.signal import TradeSignal


class TelegramBot:
    """Async Telegram bot with command handlers and proactive messaging.

    Args:
        token: Telegram bot API token.
        chat_id: Authorized chat ID for commands and signals.
        heartbeat_chat_id: Chat ID for heartbeat messages.
        storage: Injected StorageBackend for data access.
        portfolio_manager: Injected PortfolioManager.
        signal_store: Injected SignalStore.
        starting_capital: Starting capital for P&L calculations.
    """

    def __init__(
        self,
        token: str,
        chat_id: str,
        heartbeat_chat_id: str,
        storage: StorageBackend,
        portfolio_manager: PortfolioManager,
        signal_store: SignalStore,
        starting_capital: float = 15000.0,
    ) -> None:
        self._token = token
        self._chat_id = chat_id
        self._heartbeat_chat_id = heartbeat_chat_id
        self._storage = storage
        self._portfolio = portfolio_manager
        self._signal_store = signal_store
        self._starting_capital = starting_capital
        self._bot = Bot(token=token)

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def _authorized(self, update: Update) -> bool:
        """Check if the update comes from the authorized chat.

        Args:
            update: Telegram update object.

        Returns:
            True if the update's chat ID matches the configured chat_id.
        """
        chat = update.effective_chat
        if chat is None:
            return False
        return str(chat.id) == self._chat_id

    # ------------------------------------------------------------------
    # Application builder
    # ------------------------------------------------------------------

    def _build_application(self) -> Application[Any, Any, Any, Any, Any, Any]:
        """Build a Telegram Application with all command handlers registered.

        Returns:
            A fully configured Application instance.
        """
        app: Application[Any, Any, Any, Any, Any, Any] = (
            Application.builder().token(self._token).build()
        )
        app.add_handler(CommandHandler("status", self._handle_status))
        app.add_handler(CommandHandler("portfolio", self._handle_portfolio))
        app.add_handler(CommandHandler("executed", self._handle_executed))
        app.add_handler(CommandHandler("skip", self._handle_skip))
        app.add_handler(CommandHandler("close", self._handle_close))
        app.add_handler(CommandHandler("risk", self._handle_risk))
        app.add_handler(CommandHandler("resume", self._handle_resume))
        app.add_handler(CommandHandler("help", self._handle_help))
        return app

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------

    async def _handle_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command.

        Args:
            update: Telegram update object.
            context: Callback context from python-telegram-bot.
        """
        if not self._authorized(update):
            return
        state = self._portfolio.state
        response = handle_status(state, self._starting_capital)
        if update.message:
            await update.message.reply_text(response)

    async def _handle_portfolio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /portfolio command.

        Args:
            update: Telegram update object.
            context: Callback context from python-telegram-bot.
        """
        if not self._authorized(update):
            return
        state = self._portfolio.state
        current_prices: dict[str, float] = {}
        if self._storage.exists("ohlcv/XAUUSD_daily"):
            xau_df = self._storage.read_parquet("ohlcv/XAUUSD_daily")
            current_prices["XAU/USD"] = float(xau_df.iloc[-1]["close"])
        today = datetime.date.today()
        response = handle_portfolio(state, current_prices, today)
        if update.message:
            await update.message.reply_text(response)

    async def _handle_executed(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /executed <date> [price] command.

        Args:
            update: Telegram update object.
            context: Callback context from python-telegram-bot.
        """
        if not self._authorized(update):
            return
        args = context.args or []
        if not args:
            if update.message:
                await update.message.reply_text("Usage: /executed <date> [price]")
            return
        signal_date = args[0]
        if len(args) >= 2:
            try:
                price = float(args[1])
            except ValueError:
                if update.message:
                    await update.message.reply_text(f"Invalid price: {args[1]}")
                return
        else:
            pending = self._signal_store.load_pending()
            if pending is None:
                if update.message:
                    await update.message.reply_text("No pending signal.")
                return
            price = pending.trap_order_stop
        response = handle_executed(self._portfolio, self._signal_store, signal_date, price)
        if update.message:
            await update.message.reply_text(response)

    async def _handle_skip(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /skip <date> command.

        Args:
            update: Telegram update object.
            context: Callback context from python-telegram-bot.
        """
        if not self._authorized(update):
            return
        args = context.args or []
        if not args:
            if update.message:
                await update.message.reply_text("Usage: /skip <date>")
            return
        response = handle_skip(self._signal_store, args[0])
        if update.message:
            await update.message.reply_text(response)

    async def _handle_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /close <symbol> [price] command.

        Args:
            update: Telegram update object.
            context: Callback context from python-telegram-bot.
        """
        if not self._authorized(update):
            return
        args = context.args or []
        if not args:
            if update.message:
                await update.message.reply_text("Usage: /close <symbol> [price]")
            return
        symbol = args[0]
        if len(args) >= 2:
            try:
                price = float(args[1])
            except ValueError:
                if update.message:
                    await update.message.reply_text(f"Invalid price: {args[1]}")
                return
        else:
            normalized = symbol.replace("/", "")
            if normalized == "XAUUSD" and self._storage.exists("ohlcv/XAUUSD_daily"):
                xau_df = self._storage.read_parquet("ohlcv/XAUUSD_daily")
                price = float(xau_df.iloc[-1]["close"])
            else:
                if update.message:
                    await update.message.reply_text("Price required: /close <symbol> <price>")
                return
        response = handle_close(self._portfolio, symbol, price)
        if update.message:
            await update.message.reply_text(response)

    async def _handle_risk(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /risk command.

        Args:
            update: Telegram update object.
            context: Callback context from python-telegram-bot.
        """
        if not self._authorized(update):
            return
        state = self._portfolio.state
        response = handle_risk(state)
        if update.message:
            await update.message.reply_text(response)

    async def _handle_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /resume command.

        Args:
            update: Telegram update object.
            context: Callback context from python-telegram-bot.
        """
        if not self._authorized(update):
            return
        response = handle_resume(self._portfolio)
        if update.message:
            await update.message.reply_text(response)

    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command.

        Args:
            update: Telegram update object.
            context: Callback context from python-telegram-bot.
        """
        if not self._authorized(update):
            return
        response = handle_help()
        if update.message:
            await update.message.reply_text(response)

    # ------------------------------------------------------------------
    # Polling / webhook
    # ------------------------------------------------------------------

    def start_polling(self) -> None:
        """Start the bot in long-polling mode. Blocks until stopped."""
        app = self._build_application()
        app.run_polling()

    async def process_webhook_update(self, update_data: dict[str, object]) -> None:
        """Process a single Telegram update for webhook mode (Lambda).

        Args:
            update_data: Raw update JSON from Telegram.
        """
        app = self._build_application()
        async with app:
            update = Update.de_json(update_data, app.bot)
            if update:
                await app.process_update(update)

    # ------------------------------------------------------------------
    # Proactive sending
    # ------------------------------------------------------------------

    async def send_message(self, text: str, chat_id: str | None = None) -> None:
        """Send a text message to the specified chat.

        Args:
            text: Message text.
            chat_id: Target chat ID. Defaults to the main chat_id.
        """
        target = chat_id or self._chat_id
        await self._bot.send_message(chat_id=target, text=text)

    async def send_signal_card(self, signal: TradeSignal) -> None:
        """Format and send a signal card to the main chat.

        Args:
            signal: The trade signal to format and send.
        """
        text = format_signal_card(signal)
        await self.send_message(text)

    async def send_briefing(self, data: BriefingData) -> None:
        """Format and send daily briefing to the main chat.

        Args:
            data: Briefing data bundle.
        """
        text = format_daily_briefing(data)
        await self.send_message(text)

    async def send_heartbeat(
        self,
        command: str,
        timestamp: datetime.datetime,
        duration_s: float,
        composite: float,
        signal_class: str,
    ) -> None:
        """Format and send heartbeat to the heartbeat chat.

        Args:
            command: The command that ran (e.g., "ingest").
            timestamp: When the command completed.
            duration_s: How long the command took.
            composite: Latest composite z-score.
            signal_class: Signal classification string.
        """
        text = format_heartbeat(command, timestamp, duration_s, composite, signal_class)
        await self.send_message(text, chat_id=self._heartbeat_chat_id)
