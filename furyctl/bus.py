import logging
from time import sleep

import smbus

from .common import RAMStick
from .common import FURY_BASE_RGB_ADDR_DDR4, FURY_MAX_NUM_SLOTS

FURY_DELAY = 0.02
FURY_RETRAY_NUM = 4

logger = logging.getLogger(__name__)


def check_if_addr_is_valid(bus: smbus.SMBus, slot: RAMStick) -> bool:  # pyright: ignore[reportUnknownMemberType, reportUnknownParameterType]
    addr = slot.rgb_addr

    min = FURY_BASE_RGB_ADDR_DDR4
    max = min + FURY_MAX_NUM_SLOTS

    if addr < min or addr > max:
        return False

    try:
        bus.read_byte(addr)  # pyright: ignore[reportUnknownMemberType]
        return True
    except IOError:
        return False


class RetryableSMBus:
    def __init__(self, bus: smbus.SMBus) -> None:  # pyright: ignore[reportUnknownMemberType, reportUnknownParameterType]
        self.__bus = bus  # pyright: ignore[reportUnknownMemberType]

    def smbus_write_byte_data(self, addr: int, reg: int, value: int) -> None:
        msg = f"Write byte data from register {reg:x} of {addr:x} with value={value:x}"

        for retry in range(1, FURY_RETRAY_NUM + 1):
            try:
                self.__bus.write_byte_data(addr, reg, value)  # pyright: ignore[reportUnknownMemberType]
                logger.debug(msg)
                sleep(FURY_DELAY)
                break
            except OSError as err:
                if retry == 4:
                    raise err

                logger.debug(f"{msg} failed. retrying...")
                sleep(3 * retry * FURY_DELAY)

    def smbus_read_word_data(self, addr: int, reg: int) -> int:  # pyright: ignore[reportReturnType]
        msg = f"Read word data from register {reg:x} of {addr:x}"
        for retry in range(1, FURY_RETRAY_NUM + 1):
            try:
                res = self.__bus.read_word_data(addr, reg)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

                if res == 0xFFFF:
                    raise OSError("smbus returned a invalid response")

                logger.debug(f"{msg} with res={res:x}")
                sleep(FURY_DELAY)
                return res  # pyright: ignore[reportUnknownVariableType]
            except OSError as err:
                if retry == 4:
                    raise err

                logger.debug(f"{msg} failed. retrying...")
                sleep(3 * retry * FURY_DELAY)






