"""Run the Discord bot."""

import logging
from argparse import ArgumentParser, Namespace

from bot.client import create_bot
from bot.cogs.spam import SpamProtection
from bot.config import load_config
from bot.logs import setup_logging

_LOGGER = logging.getLogger(__name__)


def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument(
        "--spam-punish",
        dest="spam_protection",
        type=SpamProtection,
        choices=SpamProtection,
        default=SpamProtection.FULL,
        help="Override the punishment severity when detecting spam.",
    )
    parser.add_argument(
        "--spam-full-log",
        dest="spam_full_log",
        action="store_true",
        help="Archive and text-log spam detections from immune users.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging()
    if args.spam_protection == SpamProtection.NONE:
        _LOGGER.warning("Skipping spam punishments due to dry-run")
    elif args.spam_protection == SpamProtection.PARTIAL:
        _LOGGER.warning("Treating all punishable users as spam resistant")
    if args.spam_full_log:
        _LOGGER.warning("Logging spam from 'Immune' users")
    config = load_config()
    create_bot(
        config,
        spam_protection=args.spam_protection,
        spam_full_log=args.spam_full_log,
    ).run(config.token, log_handler=None)


if __name__ == "__main__":
    main()
