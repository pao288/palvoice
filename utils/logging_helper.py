import discord
from datetime import datetime, timezone
import config


async def send_voice_log(bot, guild_id: int, title: str, executor_id: int | None = None,
                          target_id: int | None = None, amount: int | None = None,
                          detail: str = ""):
    settings = await bot.db.get_guild_settings(guild_id)
    channel_id = settings["log_channel_id"]
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        return

    embed = discord.Embed(title=f"📋 {title}", color=config.COLOR_INFO, timestamp=datetime.now(timezone.utc))
    if executor_id is not None:
        embed.add_field(name="対象者", value=f"<@{executor_id}>", inline=True)
    if target_id is not None:
        embed.add_field(name="関連ユーザー", value=f"<@{target_id}>", inline=True)
    if amount is not None:
        embed.add_field(name="金額", value=f"{amount:,} PAL", inline=True)
    if detail:
        embed.add_field(name="内容", value=detail, inline=False)

    await channel.send(embed=embed)
