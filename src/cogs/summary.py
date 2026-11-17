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

    async def _send_private(self, interaction: discord.Interaction, content: str):
        """Send a follow-up only the invoker can see."""
        await interaction.followup.send(
            content, ephemeral=True, allowed_mentions=discord.AllowedMentions.none()
        )

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

    # Slash-only so the reply can be ephemeral (visible only to the invoker)
    @app_commands.command(
        name="summarise",
        description="Summarise the previous messages in this channel (only visible to you)",
    )
    @app_commands.describe(
        count=f"Number of messages to summarise (default {SummaryService.DEFAULT_MESSAGES}, max {SummaryService.MAX_MESSAGES})"
    )
    async def summarise(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[
            int, 1, SummaryService.MAX_MESSAGES
        ] = SummaryService.DEFAULT_MESSAGES,
    ):
        # Defer with an ephemeral "thinking…", as the LLM call outlasts
        # Discord's 3 second response window
        await interaction.response.defer(ephemeral=True, thinking=True)

        channel = interaction.channel
        if not isinstance(channel, discord.abc.Messageable):
            await self._send_private(interaction, "I can't summarise this channel!")
            return

        target = self.service.clamp_count(count)
        scan_limit = min(max(target * FETCH_MULTIPLIER, FETCH_FLOOR), FETCH_CEILING)

        # Skip prefixed commands (e.g. !impostors) in the history
        prefix = self.bot.command_prefix
        prefixes = (prefix,) if isinstance(prefix, str) else tuple(prefix)

        # Collect newest-first, stopping once enough messages are found.
        # The interaction id works as a snowflake anchor for the history fetch.
        collected: list[ChatMessage] = []
        try:
            async for message in channel.history(
                limit=scan_limit, before=discord.Object(id=interaction.id)
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
            await self._send_private(
                interaction,
                "I don't have permission to read the message history in this channel!",
            )
            return

        collected.reverse()  # oldest-first for the service

        try:
            summary = await self.service.summarise(collected)
        except ValueError as e:
            await self._send_private(interaction, str(e))
            return
        except Exception as e:
            await self._send_private(
                interaction, f"Couldn't generate a summary!\nError: {e}"
            )
            return

        noun = "message" if len(collected) == 1 else "messages"
        header = f"**Summary of the last {len(collected)} {noun}**"

        for chunk in split_message(f"{header}\n{summary}"):
            await self._send_private(interaction, chunk)


async def setup(bot: bot.Bot):
    await bot.add_cog(Summary(bot))
