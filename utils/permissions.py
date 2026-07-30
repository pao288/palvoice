import discord


def is_admin(member: discord.Member) -> bool:
    if member is None:
        return False
    return member.guild_permissions.administrator
