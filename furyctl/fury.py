import asyncio
from collections.abc import Awaitable
import logging
from typing import Callable, final

from .bus import AsyncSMBus
from .common import (
    FURY_BASE_RGB_ADDR_DDR4,
    FURY_MAX_NUM_SLOTS,
    FuryDirection,
    FuryMode,
    FuryReg,
    FuryTransfer,
)
from .util import to_rgb_str

FURY_DELAY = 0.01
FURY_RETRAY_NUM = 4
FURY_MODEL_BEAST_DDR4 = 0x23
FURY_SIGNATURE_STRING = "FURY"

logger = logging.getLogger(__name__)


async def _check_if_addr_is_valid(bus: AsyncSMBus, slot: int) -> bool:
    min = FURY_BASE_RGB_ADDR_DDR4
    max = min + FURY_MAX_NUM_SLOTS

    if slot < min or slot > max:
        return False

    try:
        await bus.read_byte(slot)
        return True
    except IOError:
        return False


async def _smbus_write_byte_data(
    bus: AsyncSMBus, addr: int, reg: int, value: int
) -> None:
    msg = f"Write byte data from register {reg:x} of {addr:x} with value={value:x}"

    assert FURY_RETRAY_NUM > 0

    for retry in range(1, FURY_RETRAY_NUM + 1):
        try:
            await bus.write_byte_data(addr, reg, value)
            logger.debug(msg)
            await asyncio.sleep(FURY_DELAY)
            break
        except OSError as err:
            if retry == 4:
                raise err

            logger.debug(f"{msg} failed. retrying...")
            await asyncio.sleep(3 * retry * FURY_DELAY)


async def _smbus_read_word_data(bus: AsyncSMBus, addr: int, reg: int) -> int:  # pyright: ignore[reportReturnType]
    msg = f"Read word data from register {reg:x} of {addr:x}"

    assert FURY_RETRAY_NUM > 0

    for retry in range(1, FURY_RETRAY_NUM + 1):
        try:
            res = await bus.read_word_data(addr, reg)

            if res == 0xFFFF:
                raise OSError("smbus returned a invalid response")

            logger.debug(f"{msg} with res={res:x}")
            await asyncio.sleep(FURY_DELAY)
            return res
        except OSError as err:
            if retry == 4:
                raise err

            logger.debug(f"{msg} failed. retrying...")
            await asyncio.sleep(3 * retry * FURY_DELAY)


async def _check_signature_on_slot(bus: AsyncSMBus, slot: int) -> bool:
    valid = True
    await _smbus_write_byte_data(bus, slot, FuryReg.APPLY, FuryTransfer.BEGIN)

    for index, char in enumerate(FURY_SIGNATURE_STRING):
        res = await _smbus_read_word_data(bus, slot, (index + 1))
        shifted = (res >> 8) & 0xFF

        if chr(shifted) != char:
            valid = False
            break

    if valid:
        model_code = await _smbus_read_word_data(bus, slot, FuryReg.MODEL) >> 8

        if model_code != FURY_MODEL_BEAST_DDR4:
            valid = False

    await _smbus_write_byte_data(bus, slot, FuryReg.APPLY, FuryTransfer.END)
    return valid


@final
class FuryComunicator:
    def __init__(self, bus: AsyncSMBus, slots: list[int]) -> None:
        self._bus = bus
        self._slots = slots
        self._reversed_slots = list(reversed(slots))

    @classmethod
    async def connect(cls, bus: AsyncSMBus, slots: list[int]) -> FuryComunicator:
        fury_slots: list[int] = list()

        for slot in slots:
            valid_addr = await _check_if_addr_is_valid(bus, slot)

            if not valid_addr:
                continue

            valid_signature = await _check_signature_on_slot(bus, slot)

            if valid_signature:
                fury_slots.append(slot)

        if len(fury_slots) == 0:
            raise RuntimeError("not found any valid addr with valid fury signature")

        logger.info(f"found valid addrs with valid fury signature")

        return cls(bus, slots)

    async def _smbus_write_byte_data(self, addr: int, reg: int, value: int) -> None:
        await _smbus_write_byte_data(self._bus, addr, reg, value)

    async def _do_inside_a_transfer(
        self, commands: Callable[[], Awaitable[None]]
    ) -> None:
        for slot in self._reversed_slots:
            await self._smbus_write_byte_data(slot, FuryReg.APPLY, FuryTransfer.BEGIN)

        await commands()

        for slot in self._slots:
            await self._smbus_write_byte_data(slot, FuryReg.APPLY, FuryTransfer.END)

    async def _set_static_color(
        self, color: tuple[int, int, int], brightness: int
    ) -> None:
        for slot in self._slots:
            await self._smbus_write_byte_data(slot, FuryReg.MODE, FuryMode.STATIC)

            await self._smbus_write_byte_data(
                slot,
                FuryReg.DIRECTION,
                FuryDirection.BOTTOM_TO_TOP,
            )

            await self._smbus_write_byte_data(slot, FuryReg.DELAY, 0x00)
            await self._smbus_write_byte_data(slot, FuryReg.SPEED, 0x00)

            await self._smbus_write_byte_data(slot, FuryReg.NUM_SLOTS, len(self._slots))

            await self._smbus_write_byte_data(slot, FuryReg.MODE_BASE_RED, color[0])
            await self._smbus_write_byte_data(slot, FuryReg.MODE_BASE_GREEN, color[1])
            await self._smbus_write_byte_data(slot, FuryReg.MODE_BASE_BLUE, color[2])

            await self._smbus_write_byte_data(slot, FuryReg.BRIGHTNESS, brightness)

    async def _sync_slots(self) -> None:
        index = len(self._reversed_slots) - 1

        while index >= 0:
            await self._smbus_write_byte_data(
                self._reversed_slots[index],
                FuryReg.INDEX,
                index,
            )
            index -= 1

    async def set_static_color(
        self, color: tuple[int, int, int], brightness: int
    ) -> None:
        if len(self._slots) > 1:
            await self._do_inside_a_transfer(self._sync_slots)

        await self._do_inside_a_transfer(
            lambda: self._set_static_color(color, brightness)
        )

        logger.info(
            f"Successfully changed color to {to_rgb_str(color)} with {brightness}% brightness"
        )
