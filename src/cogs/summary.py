import traceback

import discord
from discord import Message, MessageType, app_commands
from discord.ext import commands
from core import bot
from custom_types.summary import ChatMessage
from services.summary_service import SummaryService

DISCORD_MESSAGE_LIMIT = 2000

# Skipped messages (bots, commands, empty) reduce the yield of a history fetch,
# so scan up to this many times the requested count, capped by a hard ceiling.
# Discord returns history in pages of 100, so scanning at least one full page
# costs nothing extra and keeps small counts from coming up empty.
FETCH_MULTIPLIER = 3
FETCH_FLOOR = 100
FETCH_CEILING = 600

SUMMARISABLE_TYPES = (MessageType.default, MessageType.reply)


def split_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> list[str]:
    """Split text into chunks of at most `limit` chars, preferring newline breaks."""
    chunks: list[str] = []
    while len(text) > limit:
        cut = text.rfind("\n", 0, limit + 1)
        if cut <= 0:
            cut = text.rfind(" ", 0, limit + 1)
        if cut <= 0:
            # No usable break point: hard cut, keeping every character
            chunks.append(text[:limit])
            text = text[limit:]
            continue
        # Drop the separator itself at the break
        if text[:cut].strip():
            chunks.append(text[:cut])
        text = text[cut + 1 :]
    if text.strip():
        chunks.append(text)
    return chunks


class Summary(commands.Cog):
    def __init__(self, bot: bot.Bot):
        self.bot = bot
        self.service = bot.summary_service

    def _is_summarisable(self, message: Message, prefixes: tuple[str, ...]) -> bool:
        if message.author.bot:
            return False
        if message.type not in SUMMARISABLE_TYPES:
            return False
        content = message.content.strip()
        if not content:
            return False
        if content.startswith(prefixes):
            return False
        return True

    # Hybrid: works as both /summarise and !summarise (the alias is prefix-only)
    @commands.hybrid_command(
        "summarise",
        aliases=["summarize"],
        description="Summarise the previous messages in this channel",
        help=f"""
/summarise [count] or !summarise [count]
    Summarise the previous messages in this channel.
    count: number of messages to summarise (default {SummaryService.DEFAULT_MESSAGES}, max {SummaryService.MAX_MESSAGES}).
    Messages from bots, bot commands and messages without text are skipped.
""",
    )
    @app_commands.describe(
        count=f"Number of messages to summarise (default {SummaryService.DEFAULT_MESSAGES}, max {SummaryService.MAX_MESSAGES})"
    )
    async def summarise(
        self,
        ctx: commands.Context,
        count: commands.Range[
            int, 1, SummaryService.MAX_MESSAGES
        ] = SummaryService.DEFAULT_MESSAGES,
    ):
        no_mentions = discord.AllowedMentions.none()
        target = self.service.clamp_count(count)
        scan_limit = min(max(target * FETCH_MULTIPLIER, FETCH_FLOOR), FETCH_CEILING)

        # ctx.prefix is "/" for a slash invocation, so ask the bot for its real
        # prefixes in order to skip prefixed commands in the history
        bot_prefixes = await self.bot.get_prefix(ctx.message)
        prefixes = (
            (bot_prefixes,) if isinstance(bot_prefixes, str) else tuple(bot_prefixes)
        )

        # For a slash invocation this defers the interaction (public "thinking…"),
        # which is required as the LLM call outlasts Discord's 3 second window.
        # ctx.message is then a placeholder carrying the interaction id, which
        # still works as the `before` anchor for the history fetch.
        async with ctx.typing():
            # Collect newest-first, stopping once enough messages are found
            collected: list[ChatMessage] = []
            try:
                async for message in ctx.channel.history(
                    limit=scan_limit, before=ctx.message
                ):
                    if not self._is_summarisable(message, prefixes):
                        continue
                    collected.append(
                        ChatMessage(
                            author=message.author.display_name,
                            content=message.clean_content,
                            timestamp=message.created_at,
                        )
                    )
                    if len(collected) >= target:
                        break
            except discord.Forbidden:
                await ctx.send(
                    "I don't have permission to read the message history in this channel!",
                    allowed_mentions=no_mentions,
                )
                return

            collected.reverse()  # oldest-first for the service

            try:
                summary = await self.service.summarise(collected)
            except ValueError as e:
                await ctx.send(str(e), allowed_mentions=no_mentions)
                return
            except Exception as e:
                await ctx.send(
                    f"Couldn't generate a summary!\nError: {e}",
                    allowed_mentions=no_mentions,
                )
                return

        noun = "message" if len(collected) == 1 else "messages"
        header = f"**Summary of the last {len(collected)} {noun}**"

        for chunk in split_message(f"{header}\n{summary}"):
            await ctx.send(chunk, allowed_mentions=no_mentions)

    async def cog_command_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.BadArgument):
            await ctx.send(
                f"Invalid count! It must be a number from 1 to {SummaryService.MAX_MESSAGES}.\n"
                "Usage: /summarise [count] or !summarise [count]",
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        # Defining a cog error handler suppresses discord.py's default logging
        traceback.print_exception(type(error), error, error.__traceback__)


async def setup(bot: bot.Bot):
    await bot.add_cog(Summary(bot))
