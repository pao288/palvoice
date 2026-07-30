import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.embeds import success_embed, error_embed, main_embed
from utils.permissions import is_admin
from cogs.admin_cog import VoiceAdminPanelView


class SetupCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="voice", description="PAL VOICEの初期セットアップ(チャンネルを作成します)")
    async def voice(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            await interaction.response.send_message(
                embed=error_embed("権限エラー", "このコマンドは管理者のみ実行できます。"), ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        guild = interaction.guild
        db = self.bot.db
        settings = await db.get_guild_settings(guild.id)

        if settings["category_id"] and guild.get_channel(settings["category_id"]):
            await interaction.followup.send(
                embed=error_embed(
                    "セットアップ済みです",
                    "PAL VOICEは既にセットアップされています。作り直す場合は、カテゴリーごと削除してから、"
                    "もう一度 /voice を実行してください。"
                ),
                ephemeral=True,
            )
            return

        everyone = guild.default_role

        category = await guild.create_category(config.CATEGORY_NAME)

        voice_text_channel = await guild.create_text_channel(config.CHANNEL_VOICE_TEXT, category=category)

        admin_overwrites = {everyone: discord.PermissionOverwrite(view_channel=False)}
        admin_channel = await guild.create_text_channel(config.CHANNEL_ADMIN, category=category, overwrites=admin_overwrites)
        log_channel = await guild.create_text_channel(config.CHANNEL_LOG, category=category, overwrites=admin_overwrites)

        create_vc = await guild.create_voice_channel(config.CREATE_VC_NAME, category=category)

        await db.update_guild_settings(
            guild.id,
            category_id=category.id,
            voice_text_channel_id=voice_text_channel.id,
            admin_channel_id=admin_channel.id,
            log_channel_id=log_channel.id,
            create_vc_id=create_vc.id,
        )

        info_embed_msg = main_embed(
            "🎤 PAL VOICE",
            f"{create_vc.mention} に参加すると、BOTからDMでVC作成の設定が届きます。\n"
            "部屋タイプ・鍵の有無・利用時間を選ぶと、自動でVCが作成されます。\n\n"
            "⚠️ DMを受け取るには、このサーバーからのDMを許可しておいてください。"
        )
        await voice_text_channel.send(embed=info_embed_msg)

        admin_embed_msg = main_embed("👑 PAL VOICE 管理パネル", "管理者のみが利用できる料金設定パネルです。")
        await admin_channel.send(embed=admin_embed_msg, view=VoiceAdminPanelView())

        await interaction.followup.send(
            embed=success_embed(
                "セットアップ完了",
                f"{voice_text_channel.mention} / {admin_channel.mention} / {log_channel.mention} / {create_vc.mention}"
            ),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SetupCog(bot))
