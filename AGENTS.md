# Project notes

This repo contains a small `discord.py` bot.

## Layout

`bot/config.py` loads `.env` and `config.json`.

`bot/client.py` creates the Discord client and loads cogs.

`bot/cogs/autorole.py` assigns the default member role.

`bot/cogs/spam.py` tracks repeated messages and applies punishments.

`bot/logs.py` configures colored console logs, rotating file logs, and the top-level `spam/` archive folder.

`tests/` uses fake Discord objects. Do not require a real Discord token for tests.

## Rules

Do not add packages unless the plan or user explicitly allows it.

Keep Discord-facing code in cogs and put testable behavior in plain functions or small classes.

Use `pytest`, `isort .`, `black .`, and `mypy bot tests` before handing off changes.
