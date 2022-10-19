""" Module for commands related to events

Supports the following discord commands
* /event add
* /event submit
* /event spreadsheet
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, AnyHttpUrl
import pydantic
import discord
from discord.ext import commands
from table2ascii import table2ascii, PresetStyle

from helpers.pydantic_helpers import validate_datetime, validate_time, optional_wrapper
import helpers.gspread_helpers as gh
from helpers.enums import WSEnum
from gc_context import gc

# TODO: Make a pydantic model and functions to parse from and to it instead. Or some ORM (see butterdb)
# Spreadsheet constants
EVENT_SH_NAME = "EventSheetTest"
EVENT_SH_WRITERS = [...]  # TODO: Fetch emails from config?
EVENT_MASTER_ROLE_NAME = "EventMaster"  # TODO: Make this an id instead


# Worksheet Enums
class DEvent(WSEnum):
    event_name = 0
    has_powerstage = 1


class FEventSubmissions(WSEnum):
    user_name = 0
    submission_datetime = 1
    event_name = 2
    time = 3
    video_link = 4
    powerstage_time = 5


class EventSubmissionModel(BaseModel):
    """
    Pydantic data model for an event submission
    """
    user_name: str
    submission_datetime: datetime
    event_name: str
    time: str
    video_link: AnyHttpUrl
    powerstage_time: Optional[str]

    _time_validator = pydantic.validator("time", allow_reuse=True)(validate_time)
    _powerstage_time_validator = pydantic.validator("powerstage_time", allow_reuse=True)(
        optional_wrapper(validate_time))
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
    @discord.option("event_name", description="Enter the name of the event")
    @discord.option("has_powerstage", description="Enter the name of the event", input_type=bool)
    @commands.has_role(EVENT_MASTER_ROLE_NAME)
    async def add(self, ctx: discord.ApplicationContext, event_name: str, has_powerstage: bool):
        """Command to add an event to the spreadsheet.

        Duplicate entries are not allowed. Only users with the EVENT_MASTER_ROLE_NAME role can add events.

        Args:
            ctx: A discord ApplicationContext
            event_name: The name of the event
            has_powerstage: A bool indicating if there's a powerstage in the event or not
        """
        # Add event worksheet if not exist
        ws = gh.get_or_create_worksheet(self.sh, DEvent.title(), DEvent.headers())

        row_entry = [event_name, has_powerstage]

        # if the entry is already in the worksheet, don't add it
        if row_entry[0] in gh.get_values_by_header(ws, DEvent.event_name.name):
            await ctx.send_response(f"Event '{event_name}' already exists", ephemeral=True)
            return

        gh.safe_append_row(ws, row_entry)
        await ctx.send_response(
            f"Added '{event_name}' as an event {'with' if has_powerstage else 'without'} powerstage",
            ephemeral=True
        )

    @event_cmd_group.command()
    @discord.option("event_name", description="Enter the name of the event")
    @discord.option("time", description="Enter your time in format [H:]MM:SS.ff")
    @discord.option("video_link", description="Enter a HTTP/HTTPS URL to your recording")
    @discord.option("powerstage_time", description="Enter your powerstage time in format [H:]MM:SS.ff", required=False)
    async def submit(self, ctx: discord.ApplicationContext, event_name: str, time: str, video_link: str,
                     powerstage_time: str):
        """Command to submit an entry to an event

        Duplicate entries are not allowed. Only events present in the EVENT_WS_D_EVENT_TITLE table can be submitted to.

        Args:
            ctx: A discord ApplicationContext
            event_name: The name of the event
            time: The time of the submission on the form HH+:MM:SS.ffff
            video_link: A HTTP/HTTPS URL
            powerstage_time: The time on the powerstage on the form HH+:MM:SS.ffff.
                If required in event but not entered the submission fails
        """
        await ctx.defer(ephemeral=True)
        # Validate data
        event_submission = EventSubmissionModel(
            user_name=ctx.user.name,
            submission_datetime=datetime.now(),
            event_name=event_name,
            time=time,
            video_link=video_link,
            powerstage_time=powerstage_time
        )

        row_entry = [
            dict(event_submission)[header] for header in FEventSubmissions.headers()
        ]  # Create entry with correct order
        f_event_sub_ws = gh.get_or_create_worksheet(self.sh, FEventSubmissions.title(),
                                                    FEventSubmissions.headers())

        # If the event is not in the event dimension table, reject and inform the user
        d_event_ws = gh.get_or_create_worksheet(self.sh, DEvent.title(), DEvent.headers())
        if event_submission.event_name not in (events := gh.get_values_by_header(d_event_ws, DEvent.event_name.name)):
            await ctx.followup.send(
                f"Submission rejected :x: Event {event_name} has not been registered. These events are available: {events}",
                ephemeral=True
            )
            return

        # If the exact entry already exists in the event submission fact table, reject and inform the user
        if gh.get_first_row_where_header(f_event_sub_ws, FEventSubmissions.video_link.name,
                                         event_submission.video_link):
            await ctx.followup.send(
                f"Submission rejected :x: Video link {video_link} has already been submitted.",
                ephemeral=True
            )
            return

        # If the event has a powerstage and the powerstage time was not entered, reject.
        event_row = gh.get_first_row_where_header(d_event_ws, DEvent.event_name.name, event_submission.event_name)
        event_has_powerstage = gh.str2bool(event_row[DEvent.has_powerstage.value])
        if event_has_powerstage and not powerstage_time:
            await ctx.followup.send(
                f"Submission rejected :x: Event {event_name} requires powerstage_time to be entered",
                ephemeral=True
            )
            return

        # If event does not have a powerstage, but powerstage time was entered, reject
        if not event_has_powerstage and powerstage_time:
            await ctx.followup.send(
                f"Submission rejected :x: Event {event_name} does not have a powerstage. Hence powerstage time "
                f"should not be entered",
                ephemeral=True
            )
            return

        # Add event submission to the event submission fact table
        gh.safe_append_row(f_event_sub_ws, row_entry)

        await ctx.followup.send(
            f"Submission accepted :white_check_mark: Event was submitted successfully",
            ephemeral=True,
        )

    @event_cmd_group.command()
    @discord.option("event_name", description="Enter the name of the event")
    @discord.option("public", description="If the posted standings should be visible to everyone",
                    required=False, default=False)
    async def standings(self, ctx: discord.ApplicationContext, event_name: str, public: bool):
        """Command to get standings for an event

        Args:
            ctx: A discord ApplicationContext
            event_name: A name of an event
            public: If the results of the call should be shared publicly or not
        """
        await ctx.defer(ephemeral=not public)
        f_event_sub_ws = gh.get_or_create_worksheet(self.sh, FEventSubmissions.title(),
                                                    FEventSubmissions.headers())

        # Get all times for specified event
        event_subs = gh.get_rows_where_header(f_event_sub_ws, FEventSubmissions.event_name.name, event_name)

        # if the event has no submissions return
        if not any(event_name in event_sub for event_sub in event_subs):
            await ctx.followup.send(f"Event '{event_name}' has no submissions", ephemeral=True)
            return

        # Sort times from lowest to highest
        sorted_subs = sorted(event_subs, key=lambda x: x[FEventSubmissions.time.value])

        # Filter out top time per user
        filtered_subs = []
        processed_users = set()
        for row in sorted_subs:
            user = row[FEventSubmissions.user_name.value]
            if user in processed_users:
                continue
            processed_users.add(user)
            filtered_subs.append(row)

        # Format table
        ranked_subs = [[i + 1] + x for i, x in enumerate(filtered_subs)]
        table = table2ascii(
            header=["rank"] + FEventSubmissions.headers(),
            body=ranked_subs,
            style=PresetStyle.thin_compact
        )
        await ctx.followup.send(
            f"Standings for {event_name} \n```{table}```\n",
            ephemeral=True,
        )

    @spreadsheet.error
    async def spreadsheet_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Error handling for /event spreadsheet. Sends the error message to the caller

        Args:
            ctx: A discord ApplicationContext
            error: An exception
        """
        await ctx.send_response(f":warning: Unexpected error when calling /event spreadsheet: {str(error)}",
                                ephemeral=True)

    @add.error
    async def add_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Error handling for /event add. Sends the error message to the caller

        Args:
            ctx: A discord ApplicationContext
            error: An exception
        """
        await ctx.send_response(f":warning: Unexpected error when calling /event add: {str(error)}", ephemeral=True)

    @submit.error
    async def submit_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Error handling for /event submit. Sends the error message to the caller

        Args:
            ctx: A discord ApplicationContext
            error: An exception
        """
        await ctx.followup.send(f":warning: Unexpected error when calling /event submit: {str(error)}", ephemeral=True)

    @standings.error
    async def standings_error(self, ctx: discord.ApplicationContext, error: Exception):
        """Error handling for /event standings. Sends the error message to the caller

        Args:
            ctx: A discord ApplicationContext
            error: An exception
        """
        await ctx.followup.send(f":warning: Unexpected error when calling /event standings: {str(error)}",
                                ephemeral=True)


def setup(bot: discord.Bot):
    """ Adds the EventCommands cog to a discord Bot.

    This is called by Pycord when setting up the bot, see https://guide.pycord.dev/popular-topics/cogs/

    Args:
        bot: A discord Bot
    """
    bot.add_cog(EventCommands(bot))
