# Discord bot

A small `discord.py` bot built for a single server. It assigns a role to new
members and handles repeated cross-channel spam.

## What it does

- Assigns a configured role when a member joins.
- Detects users who repeat the same text or attachments across several channels.
- Matches message text against configurable, case-insensitive regular expressions.
- Kicks spammers by default. Members with a resistant role are timed out instead.
- Ignores members with an immune role or administrator permission.
- Logs punishments and archives the detected message under `spam/`.

## Requirements

- Python 3.11 or newer
- A Discord bot with the Server Members Intent and Message Content Intent enabled
- Permission to manage roles, messages, timeouts, and kicks in the server

The bot's role must sit above the member role and any members it may punish.

## Setup

Create a virtual environment and install the dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` with the bot token:

```dotenv
DISCORD_TOKEN=your-token
```

Create `config.json` in the project root using `config.schema.json` as the
reference. The schema documents every setting and provides editor validation.
Set `log_channel_id` to `null` to disable Discord logging.

Start the bot from the project root:

```bash
python -m bot
```

Repeated-message detection compares trimmed text and attachment contents. Repeats
in one channel do not trigger it. Editing a message replaces its previous entry in
the detection window.

Run `python -m bot --help` to see the dry-run, partial-punishment, and immune-user
logging options.

## Development

Run the checks with the virtual environment active:

```bash
pytest
isort .
black .
mypy bot tests
```
