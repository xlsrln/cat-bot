""" Module for commands related to events

Supports the following discord commands
* /event add
* /event submit
* /event spreadsheet
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, AnyHttpUrl
import pydantic
import discord
from discord.ext import commands

from helpers.pydantic_helpers import validate_datetime, validate_time
import helpers.gspread_helpers as gh
from gc_context import gc

# TODO: Make a pydantic model and functions to parse from and to it instead. Or some ORM (see butterdb)
# Spreadsheet constants
EVENT_SH_NAME = "EventSheetTest"
EVENT_SH_WRITERS = [...]  # TODO: Fetch emails from config?
EVENT_MASTER_ROLE_NAME = "EventMaster"  # TODO: Make this an id instead

# Worksheet constants
EVENT_WS_D_EVENT_TITLE = "d_event"
EVENT_WS_D_EVENT_HEADERS = ["name"]
EVENT_WS_F_EVENT_SUBMISSIONS_TITLE = "f_event_submissions"
EVENT_WS_F_EVENT_SUBMISSIONS_HEADERS = ["name", "submission_datetime", "event", "time", "video_link"]


async def get_event_names(ctx: discord.AutocompleteContext) -> List[str]:
    """Returns list to help autocomplete event names

    Args:
        ctx: A discord AutocompleteContext

    Returns:
        A list of events which matches the current text
    """
    sh = gh.get_or_create_spreadsheet(gc, EVENT_SH_NAME, EVENT_SH_WRITERS)
    ws = gh.get_or_create_worksheet(sh, EVENT_WS_D_EVENT_TITLE, EVENT_WS_D_EVENT_HEADERS)
    values = gh.get_values_by_header(ws, EVENT_WS_D_EVENT_HEADERS[0])
    return [value for value in values if str(values).lower().startswith(ctx.value.lower())]


class EventSubmissionModel(BaseModel):
    """
    Pydantic data model for an event submission
    """
    name: str
    submission_datetime: datetime
    event: str
    time: str
    video_link: AnyHttpUrl

    _time_validator = pydantic.validator("time", allow_reuse=True)(validate_time)
    _submission_datetime_validator = pydantic.validator("submission_datetime", allow_reuse=True)(validate_datetime)


class EventCommands(commands.Cog):
    """Collection of commands related to events"""
    event_cmd_group = discord.SlashCommandGroup("event", "Actions related to an event")

    def __init__(self, bot: discord.Bot):
        """Initializes EventCommands objects

        Args:
            bot: A discord Bot
        """
        self.bot = bot
        self.sh = gh.get_or_create_spreadsheet(gc, EVENT_SH_NAME, EVENT_SH_WRITERS)

    @event_cmd_group.command()
    async def spreadsheet(self, ctx: discord.ApplicationContext):
        """Command to get a link to the spreadsheet

        Args:
            ctx: A discord ApplicationContext
        """
        await ctx.send_response(f"Spreadsheet available at: {self.sh.url}", ephemeral=True)

    @event_cmd_group.command()
    @discord.option("name", description="Enter the name of the event")
    @commands.has_role(EVENT_MASTER_ROLE_NAME)
    async def add(self, ctx: discord.ApplicationContext, name: str):
        """Command to add an event to the spreadsheet.

        Duplicate entries are not allowed. Only users with the EVENT_MASTER_ROLE_NAME role can add events.

        Args:
            ctx: A discord ApplicationContext
            name: The name of the event
        """
        # Add event worksheet if not exist
        ws = gh.get_or_create_worksheet(self.sh, EVENT_WS_D_EVENT_TITLE, EVENT_WS_D_EVENT_HEADERS)

        row_entry = [name]
        # if the entry is already in the worksheet, don't add it
        if row_entry in gh.get_values(ws):
            await ctx.send_response(f"Event '{name}' already exists", ephemeral=True)
            return

        gh.safe_append_row(ws, row_entry)
        await ctx.send_response(f"Added '{name}' as an event", ephemeral=True)

    @event_cmd_group.command()
    @discord.option("event", description="Enter the name of the event",
                    autocomplete=get_event_names)  # TODO: auto-complete is broken, but waiting for fix from pycord.
    @discord.option("time", description="Enter your time in format [H:]MM:SS.ff")
    @discord.option("video_link", description="Enter a HTTP/HTTPS URL to your recording")
    async def submit(self, ctx: discord.ApplicationContext, event: str, time: str, video_link: str):
        """Command to submit an entry to an event

        Duplicate entries are not allowed. Only events present in the EVENT_WS_D_EVENT_TITLE table can be submitted to.

        Args:
            ctx: A discord ApplicationContext
            event: The name of the event
            time: The time of the submission on the form HH+:MM:SS.ffff
            video_link: A HTTP/HTTPS URL
        """
        # TODO: Add powerstage time as input

        # Validate data
        event_submission = EventSubmissionModel(
            name=ctx.user.name,
            submission_datetime=datetime.now(),
            event=event,
            time=time,
            video_link=video_link
        )

        row_entry = [
            dict(event_submission)[header] for header in EVENT_WS_F_EVENT_SUBMISSIONS_HEADERS
        ]  # Create entry with correct order
        ws = gh.get_or_create_worksheet(self.sh, EVENT_WS_F_EVENT_SUBMISSIONS_TITLE,
                                        EVENT_WS_F_EVENT_SUBMISSIONS_HEADERS)

        # If the event is not in the event dimension table, reject and inform the user
        d_event_ws = gh.get_or_create_worksheet(self.sh, EVENT_WS_D_EVENT_TITLE, EVENT_WS_D_EVENT_HEADERS)
        if event_submission.event not in (events := gh.get_values_by_header(d_event_ws, EVENT_WS_D_EVENT_HEADERS[0])):
            await ctx.send_response(
                f"Event {event_submission.event} has not been registered. These events are available: {events}",
                ephemeral=True,
            )
            return

        # If the exact entry already exists in the event submission fact table, reject and inform the user
        if row_entry in gh.get_values(ws):
            await ctx.send_response(
                f"Event submission {dict(event_submission)} has already been submitted",
                ephemeral=True,
            )
            return

        # Add event submission to the event submission fact table
        gh.safe_append_row(ws, row_entry)

        await ctx.send_response(
            f"Event {dict(event_submission)} was submitted successfully",
            ephemeral=True,
        )

    @spreadsheet.error
    async def spreadsheet_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Error handling for /event spreadsheet. Sends the error message to the caller

        Args:
            ctx: A discord ApplicationContext
            error: An exception
        """
        await ctx.send_response(f"Error when calling /event spreadsheet: {str(error)}", ephemeral=True)

    @add.error
    async def add_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Error handling for /event add. Sends the error message to the caller

        Args:
            ctx: A discord ApplicationContext
            error: An exception
        """
        await ctx.send_response(f"Error when calling /event add: {str(error)}", ephemeral=True)

    @submit.error
    async def submit_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Error handling for /event submit. Sends the error message to the caller

        Args:
            ctx: A discord ApplicationContext
            error: An exception
        """
        await ctx.send_response(f"Error when calling /event submit: {str(error)}", ephemeral=True)


def setup(bot: discord.Bot):
    """ Adds the EventCommands cog to a discord Bot.

    This is called by Pycord when setting up the bot, see https://guide.pycord.dev/popular-topics/cogs/

    Args:
        bot: A discord Bot
    """
    bot.add_cog(EventCommands(bot))
