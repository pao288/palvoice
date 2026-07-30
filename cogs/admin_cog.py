import discord
from discord.ext import commands

from utils.embeds import success_embed, error_embed, info_embed
from utils.permissions import is_admin
from utils.logging_helper import send_voice_log


RATE_LABELS = {
    "rate_3": "3時間料金",
    "rate_6": "6時間料金",
    "rate_8": "8時間料金",
    "rate_12": "12時間料金",
    "rate_18": "18時間料金",
    "rate_24": "24時間料金",
    "extend_rate": "30分延長料金",
    "monthly_rate": "指定個室1か月プラン料金",
}


class RateModal(discord.ui.Modal):
    def __init__(self, column: str):
        super().__init__(title=f"{RATE_LABELS[column]}の設定")
        self.column = column
        self.amount_input = discord.ui.TextInput(label="金額(PAL・半角数字)", max_length=15)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction):
        text = self.amount_input.value.strip()
        if not text.isdigit() or int(text) <= 0:
            await interaction.response.send_message(embed=error_embed("入力エラー", "1以上の半角数字で入力してください。"), ephemeral=True)
            return
        amount = int(text)

        db = interaction.client.db
        await db.update_guild_settings(interaction.guild_id, **{self.column: amount})

        desc = f"{RATE_LABELS[self.column]} → {amount:,} PAL"
        await interaction.response.send_message(embed=success_embed("設定を保存しました", desc), ephemeral=True)
        await send_voice_log(interaction.client, interaction.guild_id, "料金設定(管理者操作)", interaction.user.id, detail=desc)


class VoiceAdminPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_admin(interaction.user):
            await interaction.response.send_message(embed=error_embed("権限エラー", "この操作は管理者のみ行えます。"), ephemeral=True)
            return False
        return True

    @discord.ui.button(label="3時間料金", style=discord.ButtonStyle.primary, row=0, custom_id="palvoice_rate_3")
    async def rate_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal("rate_3"))

    @discord.ui.button(label="6時間料金", style=discord.ButtonStyle.primary, row=0, custom_id="palvoice_rate_6")
    async def rate_6(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal("rate_6"))

    @discord.ui.button(label="8時間料金", style=discord.ButtonStyle.primary, row=0, custom_id="palvoice_rate_8")
    async def rate_8(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal("rate_8"))

    @discord.ui.button(label="12時間料金", style=discord.ButtonStyle.primary, row=0, custom_id="palvoice_rate_12")
    async def rate_12(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal("rate_12"))

    @discord.ui.button(label="18時間料金", style=discord.ButtonStyle.primary, row=1, custom_id="palvoice_rate_18")
    async def rate_18(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal("rate_18"))

    @discord.ui.button(label="24時間料金", style=discord.ButtonStyle.primary, row=1, custom_id="palvoice_rate_24")
    async def rate_24(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal("rate_24"))

    @discord.ui.button(label="30分延長料金", style=discord.ButtonStyle.secondary, row=1, custom_id="palvoice_extend_rate")
    async def extend_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal("extend_rate"))

    @discord.ui.button(label="指定個室1か月プラン料金", style=discord.ButtonStyle.secondary, row=1, custom_id="palvoice_monthly_rate")
    async def monthly_rate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RateModal("monthly_rate"))


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
