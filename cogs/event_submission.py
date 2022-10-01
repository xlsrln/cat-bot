from datetime import  datetime
from pydantic import BaseModel, AnyHttpUrl
import pydantic
import discord
from discord.ext import commands

from helpers.pydantic_helpers import validate_datetime, validate_time


class EventSubmissionModel(BaseModel):
    """
    Data model for submitting a time to an event
    """
    name: str
    submission_datetime: datetime
    event: str
    time: str
    video_link: AnyHttpUrl

    _time_validator = pydantic.validator("time", allow_reuse=True)(validate_time)
    _submission_datetime_validator = pydantic.validator("submission_datetime", allow_reuse=True)(validate_datetime)


class EventCommands(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot

    @discord.slash_command()
    @discord.option("event", description="Enter the name of the event",
                    choices=["test1", "test2"])  # TODO: Need to fetch available events
    @discord.option("time", description="Enter your time in format [H:]MM:SS.ff")
    @discord.option("video_link", description="Enter a HTTP/HTTPS URL to your recording")
    async def test(self, ctx: discord.ApplicationContext, event, time, video_link):
        # Validate data
        event_submission = EventSubmissionModel(
            name=ctx.user.name,
            submission_datetime=datetime.now(),
            event=event,
            time=time,
            video_link=video_link
        )

        await ctx.send(event_submission)


def setup(bot):  # this is called by Pycord to setup the cog
    bot.add_cog(EventCommands(bot))  # add the cog to the bot
