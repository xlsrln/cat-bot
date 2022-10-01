#!/usr/bin/python3
import os

from pathlib import Path

import discord
from helpers.discord_helpers import get_token_from_file

#from models import EventSubmission
# Init discord bot
# The token should be in the .env file on the form "DISCORD_TOKEN=<token>"
# It should be retrieved from the discord developer page.

bot = discord.Bot()

# Init gspread
# The service account JSON file can be retrieved from the Google Developers Console.
# See https://docs.gspread.org/en/latest/oauth2.html
#gc = gspread.service_account(str(Path(__file__).parent / '.service_account.json'))

# TODO: Make this a modal as well!


if __name__ == '__main__':
    bot.load_extension('cogs.event_submission')
    # TODO: Add a create event for admins?
    bot.run(os.getenv('TOKEN') or get_token_from_file(Path(__file__).parent / '.env'))
