# Discord bot

A small `discord.py` bot for one server. It gives new members a role and watches for repeated cross-channel spam and configured spam text patterns.

## Setup

1. Install Python dependencies: `pip install -r requirements.txt`
2. Create `.env` with `DISCORD_TOKEN=your-token`
3. Create `config.json`. Use `config.schema.json` for editor validation.
4. Run the bot: `python -m bot`

The bot needs the member intent and message content intent enabled in the Discord developer portal.

## Config

Use `config.schema.json` as the reference for `config.json`.

## Behavior

When a member joins, the bot grants the role named by `member_role`.

Spam detection compares message text and attachment contents. If one user posts the same message in enough different channels inside the configured window, the bot deletes the matched messages and kicks the user. If the user has a resistant role, the bot deletes the messages and times them out instead.

Messages matching any case-insensitive regular expression in `spam_regex_patterns` trigger the same punishment immediately. Patterns use Python regular expression syntax; backslashes must be escaped in JSON, such as `"free\\s+nitro"`.

Repeating a message in one channel is ignored. Posting different messages across channels is ignored.

Spam punishments go to the console and the rotating `logs/info.log` file. The bot also archives flagged message text and attachments under `spam/<hash>/`. If `log_channel_id` is set, kick and mute logs are sent to that Discord channel.

Run `python -m bot --help` for command-line options.

## Checks

Run these before handing off changes:

```bash
pytest
isort .
black .
mypy bot tests
```
