# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false
import asyncio
import logging

import pyudev  # pyright: ignore[reportMissingTypeStubs]

from .common import FURY_BASE_RGB_ADDR_DDR4, FURY_MAX_NUM_SLOTS

BASE_SPD_ADDR = 0x50
JEDEC_KINGSTON = 0x0117

logger = logging.getLogger(__name__)


def _spd_get_jedec_id(spd: bytearray):
    return (spd[0x140] << 8) + (spd[0x141] & 0x7F) - 1


def _read_spd(spd_path: str) -> bytearray:
    with open(spd_path, "rb") as f:
        return bytearray(f.read())


async def udev_ram_detect(context: pyudev.Context):
    bus_num: int | None = None
    slots: list[int] = list()

    devices = await asyncio.to_thread(context.list_devices, DRIVER="ee1004")

    for device in devices:
        spd_path = f"{device.sys_path}/eeprom"
        spd = await asyncio.to_thread(_read_spd, spd_path)

        if _spd_get_jedec_id(spd) != JEDEC_KINGSTON:
            continue

        bus_str, addr_str = device.sys_name.split("-")  # pyright: ignore[reportUnknownVariableType]

        if bus_num is None:
            bus_num = int(bus_str)

        hex_addr = int(addr_str, 16)
        index = hex_addr - BASE_SPD_ADDR
        rgb_addr = index + FURY_BASE_RGB_ADDR_DDR4
        slots.append(rgb_addr)

    if bus_num is None:
        raise RuntimeError("invalid bus number found")

    if len(slots) == 0:
        raise RuntimeError("not found any valid Kingston DRAM")

    if len(slots) > FURY_MAX_NUM_SLOTS:
        raise RuntimeError("more than 4 sticks are not supported")

    logger.info(f"found Kingston DRAM on smbus {bus_num}")

    return bus_num, slots
