from enum import IntEnum

FURY_MAX_NUM_SLOTS = 4
FURY_BASE_RGB_ADDR_DDR4 = 0x58


class FuryTransfer(IntEnum):
    END = 0x44
    BEGIN = 0x53


class FuryDirection(IntEnum):
    BOTTOM_TO_TOP = 0x01
    TOP_TO_BOTTOM = 0x02


class FuryMode(IntEnum):
    STATIC = 0x00


class FuryReg(IntEnum):
    MODEL = 0x06
    APPLY = 0x08
    MODE = 0x09
    INDEX = 0x0B
    DIRECTION = 0x0C
    DELAY = 0x0D
    SPEED = 0x0E
    BRIGHTNESS = 0x20
    NUM_SLOTS = 0x27
    MODE_BASE_RED = 0x31
    MODE_BASE_GREEN = 0x32
    MODE_BASE_BLUE = 0x33
