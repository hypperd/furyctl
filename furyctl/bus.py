# pyright: reportUnknownMemberType=false, reportUnknownParameterType=false
# pyright: reportUnknownArgumentType=false,  reportUnknownVariableType=false
import asyncio
from typing import final

import smbus


@final
class AsyncSMBus:
    def __init__(self, bus: smbus.SMBus) -> None:
        self._bus = bus
        self._lock = asyncio.Lock()

    @classmethod
    async def connect(cls, bus_num: int):
        def sync_smbus():
            return smbus.SMBus(bus_num)

        bus = await asyncio.to_thread(sync_smbus)
        return cls(bus)

    async def write_byte_data(self, addr: int, reg: int, value: int) -> None:
        async with self._lock:
            await asyncio.to_thread(self._bus.write_byte_data, addr, reg, value)

    async def read_word_data(self, addr: int, reg: int) -> int:
        async with self._lock:
            return await asyncio.to_thread(self._bus.read_word_data, addr, reg)

    async def read_byte(self, addr: int) -> int:
        async with self._lock:
            return await asyncio.to_thread(self._bus.read_byte, addr)

    async def close(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._bus.close)
