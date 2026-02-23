import asyncio
import logging
from typing import final

from dbus_fast import BusType
from dbus_fast.aio import MessageBus
import pyudev  # pyright: ignore[reportMissingTypeStubs]

from .bus import AsyncSMBus
from .fury import FuryComunicator
from .systemd import LogindService
from .udev import udev_ram_detect
from .util import from_rgb_str

DEFAULT_BRIGHTNESS = 30
DEFAULT_COLOR = "#ffffff"

logger = logging.getLogger(__name__)


@final
class RGBManager:
    def __init__(
        self,
        finalize_event: asyncio.Event,
        logind: LogindService,
        communicator: FuryComunicator,
    ) -> None:
        self._logind = logind
        self._communicator = communicator
        self._finalize_event = finalize_event
        self._action_task: asyncio.Task[None] | None = None

        self._logind.on_prepare_for_sleep(self._on_prepare_for_sleep)

    def _run_color_change(self):
        self._action_task = asyncio.create_task(
            self._communicator.set_static_color(
                from_rgb_str(DEFAULT_COLOR), DEFAULT_BRIGHTNESS
            )
        )

        def on_done(task: asyncio.Task[None]):
            self._action_task = None
            exception = task.exception()

            if exception:
                logger.exception(exception)

        self._action_task.add_done_callback(on_done)

    def _on_prepare_for_sleep(self, going_down: bool):
        if going_down:
            return

        logging.info("waking from suspend, reapplying rgb color...")
        self._run_color_change()

    async def wait(self):
        self._run_color_change()
        await self._finalize_event.wait()

        if self._action_task is not None and not self._action_task.done():
            logger.info("finalize event received, waiting pending color change...")
            await self._action_task

    @classmethod
    async def connect(cls, finalize_event: asyncio.Event) -> RGBManager:
        dbus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        logind = await LogindService.connect(dbus)

        udev = pyudev.Context()
        bus_num, slots = await udev_ram_detect(udev)

        smbus = await AsyncSMBus.connect(bus_num)
        communicator = await FuryComunicator.connect(smbus, slots)

        return cls(finalize_event, logind, communicator)
