"""Portfolio state manager: tracks positions, drawdown, and JSON persistence.

Implements a state machine with hysteresis for drawdown throttling.
State is persisted via StorageBackend as JSON.
"""

import datetime
import enum
from dataclasses import dataclass, replace

from trading_advisor.storage.base import StorageBackend

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_DD_HALT: float = 0.15
_DD_MAX1: float = 0.12
_DD_THROTTLE: float = 0.08
_DD_RECOVERY_NORMAL: float = 0.06


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------


class ThrottleState(enum.Enum):
    """Drawdown-based throttle levels for the portfolio."""

    NORMAL = "NORMAL"
    THROTTLED_50 = "THROTTLED_50"
    THROTTLED_MAX1 = "THROTTLED_MAX1"
    HALTED = "HALTED"


# ------------------------------------------------------------------
# Value objects
# ------------------------------------------------------------------


@dataclass(frozen=True)
class Position:
    """An open position in the portfolio.

    Attributes:
        symbol: Instrument identifier.
        entry_price: Price at which the position was opened.
        size: Number of units (lots).
        entry_date: Date the position was opened.
        stop_loss: Stop-loss price level.
        take_profit: Take-profit price level.
        signal_atr: ATR value at signal time.
        is_partial: True if this position was partially closed.
        highest_high: Highest high since entry (for trailing stops).
    """

    symbol: str
    entry_price: float
    size: float
    entry_date: datetime.date
    stop_loss: float
    take_profit: float
    signal_atr: float
    is_partial: bool = False
    highest_high: float = 0.0


@dataclass(frozen=True)
class PortfolioState:
    """Immutable snapshot of the portfolio.

    Attributes:
        cash: Current cash balance (equity proxy).
        positions: Tuple of open positions.
        high_water_mark: Highest equity value ever recorded.
        throttle_state: Current drawdown throttle level.
        closed_trades: Tuple of closed trade records.
    """

    cash: float = 0.0
    positions: tuple[Position, ...] = ()
    high_water_mark: float = 0.0
    throttle_state: ThrottleState = ThrottleState.NORMAL
    closed_trades: tuple[dict[str, object], ...] = ()


# ------------------------------------------------------------------
# Portfolio Manager
# ------------------------------------------------------------------


class PortfolioManager:
    """Manages portfolio state with drawdown throttling and JSON persistence.

    The manager implements a state machine that escalates through throttle
    levels as drawdown increases, with hysteresis on recovery to avoid
    oscillation.

    Args:
        storage: Injected StorageBackend for persistence.
        storage_key: JSON key for the state file.
        auto_recover: True for backtesting (HALTED auto-recovers).
    """

    def __init__(
        self,
        storage: StorageBackend,
        storage_key: str = "state/portfolio",
        auto_recover: bool = False,
    ) -> None:
        """Initialise the portfolio manager.

        Args:
            storage: Injected StorageBackend for persistence.
            storage_key: JSON key for the state file.
            auto_recover: When True, HALTED state auto-recovers (for backtest).
        """
        self._storage = storage
        self._storage_key = storage_key
        self._auto_recover = auto_recover

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> PortfolioState:
        """Load and return the current portfolio state from storage.

        Returns:
            The current PortfolioState, or default if not persisted yet.
        """
        return self._load()

    def get_drawdown(self) -> float:
        """Calculate the current drawdown from the high-water mark.

        Returns:
            Drawdown as a fraction (0.0 to 1.0). Returns 0.0 if HWM is 0.
        """
        s = self._load()
        if s.high_water_mark == 0.0:
            return 0.0
        return (s.high_water_mark - s.cash) / s.high_water_mark

    def get_throttle_state(self) -> ThrottleState:
        """Return the current throttle state.

        Returns:
            The current ThrottleState from persisted state.
        """
        return self._load().throttle_state

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    def update_equity(self, equity: float) -> ThrottleState:
        """Update portfolio equity and evaluate throttle state transitions.

        This is the main state machine driver. It updates the high-water mark,
        calculates drawdown, and transitions the throttle state according to
        the escalation/recovery rules with hysteresis.

        Args:
            equity: Current portfolio equity value.

        Returns:
            The new ThrottleState after evaluation.
        """
        current = self._load()
        hwm = max(current.high_water_mark, equity)
        dd = (hwm - equity) / hwm if hwm > 0.0 else 0.0
        current_ts = current.throttle_state

        next_ts = self._evaluate_throttle(current_ts, dd)

        new_state = replace(
            current,
            cash=equity,
            high_water_mark=hwm,
            throttle_state=next_ts,
        )
        self._save(new_state)
        return next_ts

    def _evaluate_throttle(self, current: ThrottleState, dd: float) -> ThrottleState:
        """Evaluate the next throttle state given current state and drawdown.

        Args:
            current: The current throttle state.
            dd: Current drawdown as a fraction.

        Returns:
            The next throttle state.
        """
        # Escalation: always applies regardless of current state
        if dd >= _DD_HALT:
            return ThrottleState.HALTED
        if dd >= _DD_MAX1:
            # HALTED is more severe; only manual resume can exit it
            if current == ThrottleState.HALTED:
                return ThrottleState.HALTED
            return ThrottleState.THROTTLED_MAX1
        if dd >= _DD_THROTTLE:
            # If already in a higher state, stay there
            if current == ThrottleState.THROTTLED_MAX1:
                return ThrottleState.THROTTLED_MAX1
            if current == ThrottleState.HALTED:
                return ThrottleState.HALTED
            return ThrottleState.THROTTLED_50

        # Recovery (dd < 0.08)
        if current == ThrottleState.HALTED:
            if self._auto_recover:
                return ThrottleState.THROTTLED_50
            return ThrottleState.HALTED
        if current == ThrottleState.THROTTLED_MAX1:
            return ThrottleState.THROTTLED_50
        if current == ThrottleState.THROTTLED_50:
            if dd < _DD_RECOVERY_NORMAL:
                return ThrottleState.NORMAL
            return ThrottleState.THROTTLED_50
        return ThrottleState.NORMAL

    # ------------------------------------------------------------------
    # Position operations
    # ------------------------------------------------------------------

    def open_position(self, position: Position) -> None:
        """Add a position to the portfolio and deduct cost from cash.

        Args:
            position: The Position to open.
        """
        current = self._load()
        cost = position.size * position.entry_price
        new_state = replace(
            current,
            cash=current.cash - cost,
            positions=current.positions + (position,),
        )
        self._save(new_state)

    def close_position(self, symbol: str, exit_price: float, size: float) -> float:
        """Close (fully or partially) a position and record the trade.

        Args:
            symbol: Symbol of the position to close.
            exit_price: Price at which the position is closed.
            size: Number of units to close.

        Returns:
            The realized P&L for the closed portion.

        Raises:
            ValueError: If no position with the given symbol is found.
        """
        if size <= 0:
            raise ValueError("close size must be positive")

        current = self._load()
        pos_idx: int | None = None
        for i, p in enumerate(current.positions):
            if p.symbol == symbol:
                pos_idx = i
                break
        if pos_idx is None:
            msg = f"No open position found for symbol: {symbol}"
            raise ValueError(msg)

        position = current.positions[pos_idx]
        if size > position.size:
            raise ValueError("close size exceeds position size")

        pnl = (exit_price - position.entry_price) * size
        proceeds = size * exit_price

        positions_list = list(current.positions)
        if size >= position.size:
            # Full close
            positions_list.pop(pos_idx)
        else:
            # Partial close
            updated = replace(
                position,
                size=position.size - size,
                is_partial=True,
            )
            positions_list[pos_idx] = updated

        trade_record: dict[str, object] = {
            "symbol": symbol,
            "entry_price": position.entry_price,
            "exit_price": exit_price,
            "size": size,
            "pnl": pnl,
            "entry_date": position.entry_date.isoformat(),
        }

        new_state = replace(
            current,
            cash=current.cash + proceeds,
            positions=tuple(positions_list),
            closed_trades=current.closed_trades + (trade_record,),
        )
        self._save(new_state)
        return pnl

    # ------------------------------------------------------------------
    # Resume
    # ------------------------------------------------------------------

    def resume_from_halted(self) -> ThrottleState:
        """Manually resume from HALTED state.

        Evaluates current drawdown and transitions to the appropriate
        recovery state.

        Returns:
            The new ThrottleState after resumption.

        Raises:
            ValueError: If the current state is not HALTED.
        """
        current = self._load()
        if current.throttle_state != ThrottleState.HALTED:
            msg = (
                f"Can only resume from HALTED state, "
                f"current state is {current.throttle_state.value}"
            )
            raise ValueError(msg)

        hwm = current.high_water_mark
        dd = (hwm - current.cash) / hwm if hwm > 0.0 else 0.0

        if dd >= _DD_HALT:
            next_ts = ThrottleState.HALTED
        elif dd >= _DD_MAX1:
            next_ts = ThrottleState.THROTTLED_MAX1
        elif dd >= _DD_RECOVERY_NORMAL:
            next_ts = ThrottleState.THROTTLED_50
        else:
            next_ts = ThrottleState.NORMAL

        new_state = replace(current, throttle_state=next_ts)
        self._save(new_state)
        return next_ts

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(state: PortfolioState) -> dict[str, object]:
        """Serialize a PortfolioState to a JSON-compatible dictionary.

        Args:
            state: The state to serialize.

        Returns:
            A dictionary suitable for JSON persistence.
        """
        positions_list: list[dict[str, object]] = []
        for p in state.positions:
            positions_list.append(
                {
                    "symbol": p.symbol,
                    "entry_price": p.entry_price,
                    "size": p.size,
                    "entry_date": p.entry_date.isoformat(),
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "signal_atr": p.signal_atr,
                    "is_partial": p.is_partial,
                    "highest_high": p.highest_high,
                }
            )
        return {
            "cash": state.cash,
            "positions": positions_list,
            "high_water_mark": state.high_water_mark,
            "throttle_state": state.throttle_state.value,
            "closed_trades": list(state.closed_trades),
        }

    @staticmethod
    def _from_dict(data: dict[str, object]) -> PortfolioState:
        """Deserialize a dictionary to a PortfolioState.

        Args:
            data: Dictionary loaded from JSON storage.

        Returns:
            A reconstructed PortfolioState.
        """
        raw_positions = data.get("positions", [])
        if not isinstance(raw_positions, list):
            raise TypeError(f"Expected list for positions, got {type(raw_positions)}")
        positions: list[Position] = []
        for raw in raw_positions:
            if not isinstance(raw, dict):
                raise TypeError(f"Expected dict in positions, got {type(raw)}")
            positions.append(
                Position(
                    symbol=str(raw["symbol"]),
                    entry_price=float(str(raw["entry_price"])),
                    size=float(str(raw["size"])),
                    entry_date=datetime.date.fromisoformat(str(raw["entry_date"])),
                    stop_loss=float(str(raw["stop_loss"])),
                    take_profit=float(str(raw["take_profit"])),
                    signal_atr=float(str(raw["signal_atr"])),
                    is_partial=bool(raw.get("is_partial", False)),
                    highest_high=float(str(raw.get("highest_high", 0.0))),
                )
            )

        raw_trades = data.get("closed_trades", [])
        if not isinstance(raw_trades, list):
            raise TypeError(f"Expected list for closed_trades, got {type(raw_trades)}")
        closed_trades_list: list[dict[str, object]] = []
        for t in raw_trades:
            if not isinstance(t, dict):
                raise TypeError(f"Expected dict in closed_trades, got {type(t)}")
            closed_trades_list.append(dict(t))
        closed_trades = tuple(closed_trades_list)

        throttle_str = str(data.get("throttle_state", "NORMAL"))

        return PortfolioState(
            cash=float(str(data.get("cash", 0.0))),
            positions=tuple(positions),
            high_water_mark=float(str(data.get("high_water_mark", 0.0))),
            throttle_state=ThrottleState(throttle_str),
            closed_trades=closed_trades,
        )

    def _save(self, state: PortfolioState) -> None:
        """Persist the portfolio state to storage.

        Args:
            state: The state to save.
        """
        data = self._to_dict(state)
        # StorageBackend.write_json expects dict[str, Any]
        self._storage.write_json(self._storage_key, dict(data))

    def _load(self) -> PortfolioState:
        """Load the portfolio state from storage.

        Returns:
            The persisted state, or default if none exists.
        """
        if self._storage.exists(self._storage_key):
            raw = self._storage.read_json(self._storage_key)
            return self._from_dict(dict(raw))
        return PortfolioState()
