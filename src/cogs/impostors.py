from discord import Message, app_commands, Interaction, Member, Forbidden
from discord.ext import commands
from core import bot


class Impostors(commands.Cog):
    def __init__(self, bot: bot.Bot):
        self.bot = bot
        self.service = bot.impostors_service

    @commands.command("impostor")
    async def impostor(
        self,
        ctx: commands.Context,
        members: commands.Greedy[Member],
    ):
        if not members:
            await ctx.send("No players detected!\nUsage: !impostor <Members>")
            return

        try:
            for member in members:
                await member.send("You have been selected to play impostor!")

        except Forbidden as e:
            await ctx.send(f"Failed to send a message to {member}! Error: {e}")
            return

        await ctx.send("Successfully sent messages to each member!")


async def setup(bot: bot.Bot):
    await bot.add_cog(Impostors(bot))
