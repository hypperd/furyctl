import argparse
from dataclasses import dataclass
import logging
import re
import signal
import sys
import threading
from typing import List

import dbus
from dbus.mainloop.glib import DBusGMainLoop
import gi
from gi.repository import GLib
import pyudev
import smbus

from .common import FuryCtlError, RAMSlot
from .common import FURY_BASE_RGB_ADDR_DDR4
from .controller import FuryDRAMController, FuryDRAMDetector

DEFAULT_COLOR = "#ffffff"
DEFAULT_BRIGHTNESS = 30
JEDEC_KINGSTON = 0x0117
BASE_SPD_ADDR = 0x50
SPD_DDR4_SDRAM = 12

DBUS_LOGIND_SERVICE = "org.freedesktop.login1"
DBUS_LOGIND_PATH = "/org/freedesktop/login1"
DBUS_LOGIND_MANAGER_INTERFACE = "org.freedesktop.login1.Manager"

# logger = logging.getLogger(__name__)


@dataclass
class SMBusRAM:
    bus_num: int
    ram_slots: List[RAMSlot]


def udev_detect():
    bus_num = -1
    ram_slots: List[RAMSlot] = list()
    context = pyudev.Context()

    for d in context.list_devices(DRIVER="ee1004"):
        with open(f"{d.sys_path}/eeprom", "rb") as f:
            file = bytearray(f.read())

            # check if is DDR4
            if file[0x02] != SPD_DDR4_SDRAM:
                continue

            # check jedec
            if ((file[0x140] << 8) + (file[0x141] & 0x7F) - 1) != JEDEC_KINGSTON:
                continue

        if re.match("^[0-9]+-[0-9]+$", d.sys_name):
            bus, addr = d.sys_name.split("-")

            bus_num = int(bus)
            hex_addr = int(addr, 16)

            index = hex_addr - BASE_SPD_ADDR
            rgb_addr = index + FURY_BASE_RGB_ADDR_DDR4

            print(f"Found Kingston SDRAM on smbus {bus_num} with index={index}")

            ram_slots.append(RAMSlot(rgb_addr))

    if len(ram_slots) == 0 or bus_num < 0:
        raise FuryCtlError("Not found any valid Kingston SDRAM")

    return SMBusRAM(bus_num, ram_slots)


def check_fury(bus: smbus.SMBus, ram_slots: List[RAMSlot]) -> List[RAMSlot]:
    actual_rgb_slot: List[RAMSlot] = list()
    detector = FuryDRAMDetector(bus)

    for slot in ram_slots:
        if not detector.check_if_addr_is_valid(slot):
            continue

        if not detector.check_fury_signature_on_slot(slot):
            continue

        print(f"Found Valid Kingston Fury RGB SDRAM signature")
        actual_rgb_slot.append(slot)

    if len(actual_rgb_slot) == 0:
        raise FuryCtlError("Not found any valid Kingston Fury RGB SDRAM")

    return actual_rgb_slot


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=0)
    return parser.parse_args()


def create_thread(controller: FuryDRAMController):
    return threading.Thread(
        target=lambda: controller.set_static_color(
            (0xFF, 0xFF, 0xFF), DEFAULT_BRIGHTNESS
        )
    )


def signal_handler(sig, frame):
    sys.stdout.write("\n")
    sys.stdout.flush()
    sys.exit(1)


def main():
    arguments = parse_arguments()

    logging.basicConfig(
        level=max((3 - arguments.verbose) * 10, 0),
        format="%(levelname)s: %(message)s",
    )

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    ram = udev_detect()
    bus = smbus.SMBus(ram.bus_num)
    ram_slots = check_fury(bus, ram.ram_slots)
    controller = FuryDRAMController(bus, ram_slots)
    controller.set_static_color((0xFF, 0xFF, 0xFF), DEFAULT_BRIGHTNESS)

    loop = GLib.MainLoop()
    bus = dbus.SystemBus(mainloop=DBusGMainLoop())
    proxy = bus.get_object(DBUS_LOGIND_SERVICE, DBUS_LOGIND_PATH)

    def on_prepare_for_sleep(going_down: bool):
        if going_down:
            return

        logging.info("Waking from suspend, reapplying rgb color")
        thread = create_thread(controller)
        thread.start()

    proxy.connect_to_signal(
        "PrepareForSleep", on_prepare_for_sleep, DBUS_LOGIND_MANAGER_INTERFACE
    )

    loop.run()
