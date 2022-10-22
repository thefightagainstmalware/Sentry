# Sentry
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Watches your hypixel account and notifies you via discord if you login.
If it says you logged in, but you didn't, your account may be stolen.<br>
A live bot is (sometimes) running with discord id 987115802912247908. Invite with https://discord.com/api/oauth2/authorize?client_id=987115802912247908&permissions=8&scope=bot%20applications.commands
## Running locally
You need both a Hypixel API key (/api new) and a discord bot token (https://discord.com/developers)<br>
Create a file called '.env', and fill it like so
```
HYPIXEL_API_KEY=<your hypixel api key>
DISCORD_BOT_TOKEN=<your discord bot token>
MAIN_GUILD_ID=<Guildid for the main server this will be used on>
```
Install dependencies with `pip install -r requirements.txt`<br>
Run the bot with `python3 main.py`<br>
Add the bot with slash commands permissions and /watch accounts<br>
