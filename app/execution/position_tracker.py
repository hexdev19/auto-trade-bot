import asyncio
import decimal
from typing import Dict, List, Optional
from app.models.domain import OpenPosition

class PositionTracker:
    def __init__(self):
        self._positions: Dict[str, OpenPosition] = {}
        self._lock = asyncio.Lock()

    async def add(self, position: OpenPosition):
        async with self._lock:
            self._positions[position.id] = position

    async def remove(self, pos_id: str) -> Optional[OpenPosition]:
        async with self._lock:
            return self._positions.pop(pos_id, None)

    def get(self, pos_id: str) -> Optional[OpenPosition]:
        return self._positions.get(pos_id)

    def get_all(self) -> List[OpenPosition]:
        return list(self._positions.values())

    def has_position(self, symbol: str) -> bool:
        return any(p.symbol == symbol for p in self._positions.values())

    async def update_sl(self, pos_id: str, new_sl: decimal.Decimal):
        async with self._lock:
            if pos_id in self._positions:
                self._positions[pos_id].stop_loss = new_sl
