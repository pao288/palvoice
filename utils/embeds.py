import discord
import config


def success_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"✅ {title}", description=description, color=config.COLOR_SUCCESS)


def error_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=description, color=config.COLOR_ERROR)


def info_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"ℹ️ {title}", description=description, color=config.COLOR_INFO)


def main_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=config.COLOR_MAIN)
