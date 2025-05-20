import logging
from time import sleep
from typing import Callable

import smbus

from .common import FuryDirection, FuryMode, FuryReg, FuryTransaction, RAMSlot
from .common import FURY_BASE_RGB_ADDR_DDR4, FURY_MAX_NUM_SLOTS

FURY_DELAY = 0.02
FURY_MODEL_BEAST_DDR4 = 0x23

logger = logging.getLogger(__name__)


class FurySMBus:
    def __init__(self, bus: smbus.SMBus) -> None:
        self.__bus = bus

    def smbus_write_byte_data(self, addr: int, reg: int, value: int) -> None:
        for retry in range(3):
            success: bool;

            try:
                self.__bus.write_byte_data(addr, reg, value)
                logger.debug(
                    f"Write byte data from register {reg:x} of {addr:x} with value={value:x}"
                )
                success = True
            except IOError as ex:
                if retry == 2:
                    raise ex

                logger.debug(
                    f"Write byte data from register {reg:x} of {addr:x} with value={value:x} failed. retrying..."
                )

                success = False;

            sleep((retry + 1) * FURY_DELAY)

            if success:
                break;

    def smbus_read_word_data(self, addr: int, reg: int) -> int:
        res = self.__bus.read_word_data(addr, reg)
        logger.debug(
            f"Read word data from register {reg:x} of {addr:x} with res={res:x}"
        )
        sleep(FURY_DELAY)
        return res

    def smbus_read_byte(self, addr: int) -> int:
        res = self.__bus.read_byte(addr)
        logger.debug(f"Read byte from address {addr:x}")
        sleep(FURY_DELAY)
        return res


class FuryDRAMController:
    def __init__(self, bus: smbus.SMBus, slots: list[RAMSlot]) -> None:
        self.__bus = FurySMBus(bus)
        self.slots = slots
        self.reversed_slots = list(reversed(slots))

    def __do_inside_a_transaction(self, commands: Callable[[], None]) -> None:
        # Start transaction
        for slot in self.reversed_slots:
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr,
                FuryReg.FURY_REG_APPLY,
                FuryTransaction.FURY_BEGIN_TRNSFER,
            )

        # Apply commands
        commands()

        # End transaction
        for slot in self.slots:
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr,
                FuryReg.FURY_REG_APPLY,
                FuryTransaction.FURY_END_TRNSFER,
            )

    def __sync_slots(self) -> None:
        index = len(self.reversed_slots) - 1

        while index >= 0:
            self.__bus.smbus_write_byte_data(
                self.reversed_slots[index].rgb_addr,
                FuryReg.FURY_REG_INDEX,
                index,
            )
            index -= 1

    def __set_static_color(self, color: tuple[int, int, int], brightness: int) -> None:
        for slot in self.slots:
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.FURY_REG_MODE, FuryMode.FURY_MODE_STATIC
            )

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr,
                FuryReg.FURY_REG_DIRECTION,
                FuryDirection.FURY_DIR_BOTTOM_TO_TOP,
            )

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.FURY_REG_DELAY, 0x00
            )
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.FURY_REG_SPEED, 0x00
            )

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.FURY_REG_NUM_SLOTS, len(self.slots)
            )

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.FURY_REG_MODE_BASE_RED, color[0]
            )
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.FURY_REG_MODE_BASE_GREEN, color[1]
            )
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.FURY_REG_MODE_BASE_BLUE, color[2]
            )

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.FURY_REG_BRIGHTNESS, brightness
            )

    def set_static_color(self, color: tuple[int, int, int], brightness: int) -> None:
        if len(self.slots) > 1:
            self.__do_inside_a_transaction(self.__sync_slots)

        self.__do_inside_a_transaction(
            lambda: self.__set_static_color(color, brightness)
        )

class FuryDRAMDetector:
    def __init__(self, bus: smbus.SMBus) -> None:
        self.__bus = FurySMBus(bus)

    def check_fury_signature_on_slot(self, slot: RAMSlot):
        check = True
        self.__bus.smbus_write_byte_data(
            slot.rgb_addr,
            FuryReg.FURY_REG_APPLY,
            FuryTransaction.FURY_BEGIN_TRNSFER,
        )

        res = self.__bus.smbus_read_word_data(slot.rgb_addr, FuryReg.FURY_REG_MODEL)
        model_code = res >> 8

        if model_code != FURY_MODEL_BEAST_DDR4:
            check = False

        self.__bus.smbus_write_byte_data(
            slot.rgb_addr,
            FuryReg.FURY_REG_APPLY,
            FuryTransaction.FURY_END_TRNSFER,
        )

        return check

    # based on i2cdetect cli tool
    def check_if_addr_is_valid(self, slot: RAMSlot) -> bool:
        addr = slot.rgb_addr

        min = FURY_BASE_RGB_ADDR_DDR4
        max = min + FURY_MAX_NUM_SLOTS

        if addr < min or addr > max:
            return False

        try:
            self.__bus.smbus_read_byte(addr)
            return True
        except IOError:
            return False
