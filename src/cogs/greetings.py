from discord import Message
from discord.ext import commands
from core import bot


class Greetings(commands.Cog):
    def __init__(self, bot: bot.Bot):
        self.bot = bot
        self.service = bot.greetings_service

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author == self.bot.user:
            return

        if "hello" in message.content.lower():
            await message.channel.send(f"Hello {message.author}!")
            await self.service.greet()


async def setup(bot: bot.Bot):
    await bot.add_cog(Greetings(bot))
