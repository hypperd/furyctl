import logging

import pyudev

from .common import FURY_BASE_RGB_ADDR_DDR4, RAMStick, SMBusConfig

BASE_SPD_ADDR = 0x50
JEDEC_KINGSTON = 0x0117

logger = logging.getLogger(__name__)


def _jedec_id(spd: bytearray):
    return (spd[0x140] << 8) + (spd[0x141] & 0x7F) - 1


def udev_ram_detect(context: pyudev.Context) -> SMBusConfig:
    bus_num: int | None = None
    ram_slots: list[RAMStick] = list()

    for d in context.list_devices(DRIVER="ee1004"):  # pyright: ignore[reportUnknownMemberType]
        with open(f"{d.sys_path}/eeprom", "rb") as f:  # pyright: ignore[reportUnknownMemberType]
            file = bytearray(f.read())

            if _jedec_id(file) != JEDEC_KINGSTON:
                continue

        bus_str, addr_str = d.sys_name.split("-")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        bus = int(bus_str)  # pyright: ignore[reportUnknownArgumentType]

        if bus_num is not None and bus_num != bus:
            raise RuntimeError("RAM sticks not in same bus are not supported")

        hex_addr = int(addr_str, 16)  # pyright: ignore[reportUnknownArgumentType]
        bus_num = bus

        index = hex_addr - BASE_SPD_ADDR
        rgb_addr = index + FURY_BASE_RGB_ADDR_DDR4

        ram_slots.append(RAMStick(index, rgb_addr))

    logger.info(f"Found Kingston SDRAM on smbus {bus_num}")

    if bus_num is None:
        raise RuntimeError("Invalid bus number")

    if len(ram_slots) == 0:
        raise RuntimeError("Not found any valid Kingston SDRAM")

    if len(ram_slots) > 4:
        raise RuntimeError("More than 4 sticks are not supported")

    return SMBusConfig(bus_num, ram_slots)
