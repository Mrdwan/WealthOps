"""Pending trade signal persistence via StorageBackend."""

import datetime

from trading_advisor.storage.base import StorageBackend
from trading_advisor.strategy.signal import TradeSignal

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_STORAGE_KEY: str = "state/pending_signal"


# ------------------------------------------------------------------
# SignalStore
# ------------------------------------------------------------------


class SignalStore:
    """Persists pending trade signals via StorageBackend.

    Args:
        storage: Injected StorageBackend for persistence.
    """

    def __init__(self, storage: StorageBackend) -> None:
        """Initialise the store with an injected backend.

        Args:
            storage: StorageBackend to use for reading and writing signals.
        """
        self._storage = storage

    def save_pending(self, signal: TradeSignal) -> None:
        """Store a pending signal. Overwrites any existing pending signal.

        Args:
            signal: The TradeSignal to persist.
        """
        data = {
            "date": signal.date.isoformat(),
            "asset": signal.asset,
            "direction": signal.direction,
            "composite_score": signal.composite_score,
            "signal_strength": signal.signal_strength,
            "trap_order_stop": signal.trap_order_stop,
            "trap_order_limit": signal.trap_order_limit,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "trailing_stop_atr_mult": signal.trailing_stop_atr_mult,
            "position_size": signal.position_size,
            "risk_amount": signal.risk_amount,
            "risk_reward_ratio": signal.risk_reward_ratio,
            "guards_passed": list(signal.guards_passed),
            "ttl": signal.ttl,
        }
        self._storage.write_json(_STORAGE_KEY, data)

    def load_pending(self) -> TradeSignal | None:
        """Load the pending signal, or None if no signal is pending.

        Returns:
            The pending TradeSignal, or None if none exists or was cleared.
        """
        if not self._storage.exists(_STORAGE_KEY):
            return None
        raw = self._storage.read_json(_STORAGE_KEY)
        if "date" not in raw:  # cleared or empty
            return None
        return TradeSignal(
            date=datetime.date.fromisoformat(str(raw["date"])),
            asset=str(raw["asset"]),
            direction=str(raw["direction"]),
            composite_score=float(str(raw["composite_score"])),
            signal_strength=str(raw["signal_strength"]),
            trap_order_stop=float(str(raw["trap_order_stop"])),
            trap_order_limit=float(str(raw["trap_order_limit"])),
            stop_loss=float(str(raw["stop_loss"])),
            take_profit=float(str(raw["take_profit"])),
            trailing_stop_atr_mult=float(str(raw["trailing_stop_atr_mult"])),
            position_size=float(str(raw["position_size"])),
            risk_amount=float(str(raw["risk_amount"])),
            risk_reward_ratio=float(str(raw["risk_reward_ratio"])),
            guards_passed=tuple(str(g) for g in raw["guards_passed"]),
            ttl=int(str(raw["ttl"])),
        )

    def clear_pending(self) -> None:
        """Remove the pending signal.

        Writes a sentinel value so subsequent loads return None.
        """
        self._storage.write_json(_STORAGE_KEY, {"status": "cleared"})
