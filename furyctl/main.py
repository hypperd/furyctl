import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from signal import SIGINT, SIGTERM
import sys

from setproctitle import setproctitle

from .manager import RGBManager

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=0)
    return parser.parse_args()


async def start(finalize_event: asyncio.Event):
    manager = await RGBManager.connect(finalize_event)
    await manager.wait()


def main():
    setproctitle("furyctl")
    arguments = parse_arguments()

    logging.basicConfig(
        level=max((3 - arguments.verbose) * 10, 0),  # pyright: ignore[reportAny]
        format="%(levelname)s: %(message)s",
    )

    error = False
    loop = asyncio.new_event_loop()
    finalize_event = asyncio.Event()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=1))

    loop.add_signal_handler(SIGINT, lambda: finalize_event.set())
    loop.add_signal_handler(SIGTERM, lambda: finalize_event.set())

    try:
        loop.run_until_complete(start(finalize_event))
    except Exception as ex:
        logger.exception(ex)
        error = True
    finally:
        loop.close()

    if error:
        sys.exit(1)
