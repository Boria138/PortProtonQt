"""Power profile tools for PortProton scripts."""
import argparse
import asyncio
import sys

from portprotonqt.logger import get_logger
from portprotonqt.scripts_utils.dbus_tools import get_power_profile, set_power_profile


logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse arguments for power profile tools."""
    parser = argparse.ArgumentParser(description="PortProtonQt power profile tools")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("get", help="Print active power profile")

    set_parser = subparsers.add_parser("set", help="Set active power profile")
    set_parser.add_argument("profile", help="Power profile name")
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    try:
        if args.command == "get":
            profile = await get_power_profile()
            if not profile:
                return 1
            print(profile)
            return 0
        if args.command == "set":
            return 0 if await set_power_profile(args.profile) else 1
    except Exception as error:
        logger.debug("Power profile command failed: %s", error)
        return 1
    return 1


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
