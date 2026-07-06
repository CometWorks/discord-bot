"""Run the Discord bot."""

import logging
from argparse import ArgumentParser, Namespace

from bot.client import create_bot
from bot.config import load_config
from bot.logs import setup_logging

_LOGGER = logging.getLogger(__name__)


def parse_args() -> Namespace:
    parser = ArgumentParser()
    parser.add_argument(
        "--spam-dry-run",
        dest="spam_dry_run",
        action="store_true",
        help="Log spam punishments without deleting messages, kicking, or muting users.",
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
    if args.spam_dry_run:
        _LOGGER.warning("Skipping spam punishments due to dry-run")
    if args.spam_full_log:
        _LOGGER.warning("Logging spam from 'Immune' users")
    config = load_config()
    create_bot(
        config, spam_dry_run=args.spam_dry_run, spam_full_log=args.spam_full_log
    ).run(config.token, log_handler=None)


if __name__ == "__main__":
    main()
