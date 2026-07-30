# ===============================================
# main.py
# PAL VOICEの起動ファイルです。Railwayではこれを実行します。
# ===============================================

import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import Database
from cogs.admin_cog import VoiceAdminPanelView

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.default()
intents.members = True
intents.voice_states = True


class PalVoiceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.db = Database()

    async def setup_hook(self):
        await self.db.connect(DATABASE_URL)

        self.add_view(VoiceAdminPanelView())

        await self.load_extension("cogs.setup_cog")
        await self.load_extension("cogs.voice_cog")
        await self.load_extension("cogs.admin_cog")

        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ ログインしました: {self.user} (ID: {self.user.id})")


async def main():
    bot = PalVoiceBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
