"""Gestor de ejecución de órdenes con idempotencia, reconciliación tras timeout y manejo de ejecuciones parciales."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable, Dict, Optional


@dataclass
class OrderRecord:
    order_id: str
    client_order_id: str
    symbol: str
    side: str  # 'BUY' | 'SELL'
    requested_qty: float
    filled_qty: float
    avg_fill_price: float
    fee_usdt: float
    status: str  # 'FILLED' | 'PARTIALLY_FILLED' | 'PENDING_RECONCILIATION' | 'REJECTED'
    mode: str  # 'paper' | 'live'
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class OrderExecutionEngine:
    """Garantiza que no se dupliquen compras ante timeouts y reconcilia el estado antes de reintentar."""

    def __init__(self, mode: str = "paper") -> None:
        if mode not in ("demo", "paper", "live"):
            raise ValueError(f"Modo inválido: {mode}")
        self.mode = mode
        self._orders_by_client_id: Dict[str, OrderRecord] = {}
        self._unknown_state_order_ids: set[str] = set()

    @property
    def has_unknown_orders(self) -> bool:
        return len(self._unknown_state_order_ids) > 0

    def submit_order(
        self,
        client_order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        reference_price: float,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        simulate_timeout: bool = False,
        simulate_partial_ratio: Optional[float] = None,
    ) -> OrderRecord:
        # 1. Prevención de órdenes duplicadas (idempotencia por client_order_id)
        if client_order_id in self._orders_by_client_id:
            existing = self._orders_by_client_id[client_order_id]
            return existing

        # 2. Bloqueo si existe una orden previa sin reconciliar
        if self.has_unknown_orders:
            return OrderRecord(
                order_id=f"ord-rej-{len(self._orders_by_client_id)+1}",
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                requested_qty=quantity,
                filled_qty=0.0,
                avg_fill_price=0.0,
                fee_usdt=0.0,
                status="REJECTED",
                mode=self.mode,
                reason="UNKNOWN_ORDER_STATE: Reconcilie órdenes pendientes antes de enviar nuevas.",
            )

        # 3. Bloqueo de seguridad si alguien intenta enviar órdenes reales sin habilitación completa
        if self.mode == "live":
            raise PermissionError(
                "El envío directo en modo LIVE está bloqueado mientras el motor permanezca en simulación."
            )

        order_id = f"paper-ord-{len(self._orders_by_client_id)+1:05d}"

        if simulate_timeout:
            record = OrderRecord(
                order_id=order_id,
                client_order_id=client_order_id,
                symbol=symbol,
                side=side,
                requested_qty=quantity,
                filled_qty=0.0,
                avg_fill_price=0.0,
                fee_usdt=0.0,
                status="PENDING_RECONCILIATION",
                mode=self.mode,
                reason="Timeout en comunicación; requiere reconciliación antes de reintentar.",
            )
            self._orders_by_client_id[client_order_id] = record
            self._unknown_state_order_ids.add(client_order_id)
            return record

        fill_price = (
            round(reference_price * (1.0 + slippage_rate), 2)
            if side == "BUY"
            else round(reference_price * (1.0 - slippage_rate), 2)
        )

        ratio = (
            max(0.0, min(1.0, simulate_partial_ratio))
            if simulate_partial_ratio is not None
            else 1.0
        )
        filled_qty = round(quantity * ratio, 6)
        fee = round(filled_qty * fill_price * fee_rate, 6)
        status = "FILLED" if ratio >= 0.9999 else "PARTIALLY_FILLED"

        record = OrderRecord(
            order_id=order_id,
            client_order_id=client_order_id,
            symbol=symbol,
            side=side,
            requested_qty=quantity,
            filled_qty=filled_qty,
            avg_fill_price=fill_price,
            fee_usdt=fee,
            status=status,
            mode=self.mode,
            reason="Ejecución simulada en paper trading.",
        )
        self._orders_by_client_id[client_order_id] = record
        return record

    def reconcile_order(
        self,
        client_order_id: str,
        remote_status_resolver: Callable[[str], Optional[OrderRecord]],
    ) -> OrderRecord:
        """Consulta primero si la orden fue creada en el exchange antes de repetirla."""
        resolved = remote_status_resolver(client_order_id)
        if resolved is not None:
            self._orders_by_client_id[client_order_id] = resolved
            self._unknown_state_order_ids.discard(client_order_id)
            return resolved
        raise RuntimeError(f"No fue posible reconciliar la orden {client_order_id}.")
