"""AWS Lambda handler for WealthOps scheduled jobs and Telegram webhook."""

from __future__ import annotations

import json
from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda entry point.

    Dispatches to the appropriate WealthOps command based on the event payload.

    Supported events:
      - ``{"command": "ingest"}`` — run daily ingest pipeline
      - ``{"command": "briefing"}`` — send daily briefing
      - Telegram webhook update (has ``"body"`` key) — process bot command

    Args:
        event: Lambda event payload.
        context: Lambda context (unused).

    Returns:
        HTTP-style response dict with ``statusCode`` and ``body``.
    """
    # Telegram webhook (Lambda Function URL)
    if "body" in event:
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

        update_data = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        import asyncio

        asyncio.run(bot.process_webhook_update(update_data))
        return {"statusCode": 200, "body": "ok"}

    # Scheduled command (EventBridge)
    command = event.get("command", "")
    if command == "ingest":
        from trading_advisor.runner import run_ingest

        run_ingest()
        return {"statusCode": 200, "body": "ingest complete"}

    if command == "briefing":
        from trading_advisor.runner import run_briefing

        run_briefing()
        return {"statusCode": 200, "body": "briefing complete"}

    return {"statusCode": 400, "body": f"Unknown command: {command!r}"}
