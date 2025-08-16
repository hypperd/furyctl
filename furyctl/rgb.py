import logging
from typing import Callable

from .util import to_rgb_str

from .common import FuryDirection, FuryMode, FuryReg, FuryTransfer, RAMStick
from .bus import RetryableSMBus

FURY_MODEL_BEAST_DDR4 = 0x23
FURY_SIGNATURE_STRING = "FURY"

logger = logging.getLogger(__name__)


def check_signature_on_slot(bus: RetryableSMBus, slot: RAMStick):
    valid = True
    bus.smbus_write_byte_data(slot.rgb_addr, FuryReg.APPLY, FuryTransfer.BEGIN)

    for index, char in enumerate(FURY_SIGNATURE_STRING):
        res = bus.smbus_read_word_data(slot.rgb_addr, (index + 1))
        shifted = (res >> 8) & 0xFF

        if chr(shifted) != char:
            valid = False
            break

    if valid:
        model_code = bus.smbus_read_word_data(slot.rgb_addr, FuryReg.MODEL) >> 8

        if model_code != FURY_MODEL_BEAST_DDR4:
            valid = False

    bus.smbus_write_byte_data(slot.rgb_addr, FuryReg.APPLY, FuryTransfer.END)
    return valid


class RGBController:
    def __init__(self, bus: RetryableSMBus, slots: list[RAMStick]) -> None:
        self.__bus = bus
        self.__slots = slots
        self.__reversed_slots = list(reversed(slots))

    def __do_inside_a_transaction(self, commands: Callable[[], None]) -> None:
        # Start transaction
        for slot in self.__reversed_slots:
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.APPLY, FuryTransfer.BEGIN
            )

        # Apply commands
        commands()

        # End transaction
        for slot in self.__slots:
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.APPLY, FuryTransfer.END
            )

    def __sync_slots(self) -> None:
        index = len(self.__reversed_slots) - 1

        while index >= 0:
            self.__bus.smbus_write_byte_data(
                self.__reversed_slots[index].rgb_addr,
                FuryReg.INDEX,
                index,
            )
            index -= 1

    def __set_static_color(self, color: tuple[int, int, int], brightness: int) -> None:
        for slot in self.__slots:
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.MODE, FuryMode.STATIC
            )

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr,
                FuryReg.DIRECTION,
                FuryDirection.BOTTOM_TO_TOP,
            )

            self.__bus.smbus_write_byte_data(slot.rgb_addr, FuryReg.DELAY, 0x00)
            self.__bus.smbus_write_byte_data(slot.rgb_addr, FuryReg.SPEED, 0x00)

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.NUM_SLOTS, len(self.__slots)
            )

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.MODE_BASE_RED, color[0]
            )
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.MODE_BASE_GREEN, color[1]
            )
            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.MODE_BASE_BLUE, color[2]
            )

            self.__bus.smbus_write_byte_data(
                slot.rgb_addr, FuryReg.BRIGHTNESS, brightness
            )

    def set_static_color(self, color: tuple[int, int, int], brightness: int) -> None:
        if len(self.__slots) > 1:
            self.__do_inside_a_transaction(self.__sync_slots)

        self.__do_inside_a_transaction(
            lambda: self.__set_static_color(color, brightness)
        )

        logger.info(
            f"Successfully changed color to {to_rgb_str(color)} with {brightness}% brightness"
        )
