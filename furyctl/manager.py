import pyudev
import smbus
import logging
import threading

import gi
import dbus
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop

from .util import get_rgb
from .common import RAMStick
from .detect import udev_ram_detect
from .rgb import RGBController, check_signature_on_slot
from .bus import RetryableSMBus, check_if_addr_is_valid

DBUS_LOGIND_SERVICE = "org.freedesktop.login1"
DBUS_LOGIND_PATH = "/org/freedesktop/login1"
DBUS_LOGIND_MANAGER_INTERFACE = "org.freedesktop.login1.Manager"

DEFAULT_COLOR = get_rgb("#ffffff")
DEFAULT_BRIGHTNESS = 30

logger = logging.getLogger(__name__)


class FuryManager:
    __thread: threading.Thread | None = None

    def __init__(self) -> None:
        udev_ctx = pyudev.Context()
        smbus_config = udev_ram_detect(udev_ctx)

        bus = smbus.SMBus(smbus_config.bus_num)  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]

        ram_slots: list[RAMStick] = list()

        for slot in smbus_config.ram_slots:
            if not check_if_addr_is_valid(bus, slot):  # pyright: ignore[reportUnknownArgumentType]
                continue

            ram_slots.append(slot)

        if len(ram_slots) == 0:
            raise RuntimeError("All sticks dont have valid rgb addr")
        
        logger.info(f"Found slots with valid rgb address")

        ram_slots = list()
        retryable_smbus = RetryableSMBus(bus)  # pyright: ignore[reportUnknownArgumentType]

        for slot in smbus_config.ram_slots:
            if not check_signature_on_slot(retryable_smbus, slot):
                continue

            ram_slots.append(slot)

        if len(ram_slots) == 0:
            raise RuntimeError("All sticks dont have valid Fury signature")


        logger.info(f"Found slots with valid fury signature")

        self.__loop = GLib.MainLoop()
        system_bus = dbus.SystemBus(mainloop=DBusGMainLoop())  # pyright: ignore[reportUnknownArgumentType]
        self.__rgb_controller = RGBController(retryable_smbus, ram_slots)

        proxy = system_bus.get_object(DBUS_LOGIND_SERVICE, DBUS_LOGIND_PATH)  # pyright: ignore[reportUnknownMemberType]
        proxy.connect_to_signal(  # pyright: ignore[reportUnknownMemberType]
            "PrepareForSleep",
            self.__on_prepare_for_sleep,
            DBUS_LOGIND_MANAGER_INTERFACE,
        )

    def run(self):
        self.__rgb_controller.set_static_color(DEFAULT_COLOR, DEFAULT_BRIGHTNESS)
        self.__loop.run()  # pyright: ignore[reportUnknownMemberType]

    def __create_thread(self) -> threading.Thread:
        return threading.Thread(
            target=lambda: self.__rgb_controller.set_static_color(
                DEFAULT_COLOR, DEFAULT_BRIGHTNESS
            )
        )

    def __on_prepare_for_sleep(self, going_down: bool) -> None:
        if going_down:
            return

        logging.info("Waking from suspend, reapplying rgb color...")

        if self.__thread is not None and self.__thread.is_alive():
            return

        self.__thread = self.__create_thread()
        self.__thread.start()
