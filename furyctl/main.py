import argparse
import logging
import signal
import sys

from setproctitle import setproctitle

from .manager import FuryManager

logger = logging.getLogger(__name__)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=0)
    return parser.parse_args()


def signal_handler(sig, frame):
    sys.stdout.write("\n")
    sys.stdout.flush()
    sys.exit(0)

def main():
    setproctitle("furyctl")
    arguments = parse_arguments()

    logging.basicConfig(
        level=max((3 - arguments.verbose) * 10, 0),
        format="%(levelname)s: %(message)s",
    )

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    manager = FuryManager()
    manager.run()
