# ===============================================
# cogs/admin_cog.py
# 👑VOICE管理チャンネルの「料金設定パネル」です。
# 管理者(Discordの管理者権限を持つ人)だけが使えます。
# ===============================================

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


class RoleRateModal(discord.ui.Modal):
    def __init__(self, role_id: int, role_name: str, column: str):
        super().__init__(title=f"{RATE_LABELS[column]}(ロール別) - {role_name}"[:45])
        self.role_id = role_id
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
        await db.update_role_rate(interaction.guild_id, self.role_id, **{self.column: amount})

        desc = f"<@&{self.role_id}> の {RATE_LABELS[self.column]} → {amount:,} PAL"
        await interaction.response.send_message(embed=success_embed("ロール別料金を保存しました", desc), ephemeral=True)
        await send_voice_log(interaction.client, interaction.guild_id, "ロール別料金設定(管理者操作)", interaction.user.id, detail=desc)


class RoleRatePanelView(discord.ui.View):
    def __init__(self, role_id: int, role_name: str):
        super().__init__(timeout=180)
        self.role_id = role_id
        self.role_name = role_name
        for column in RATE_LABELS.keys():
            btn = discord.ui.Button(label=RATE_LABELS[column], style=discord.ButtonStyle.primary)
            btn.callback = self._make_callback(column)
            self.add_item(btn)

    def _make_callback(self, column: str):
        async def callback(interaction: discord.Interaction):
            await interaction.response.send_modal(RoleRateModal(self.role_id, self.role_name, column))
        return callback


class RoleSelectForRateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.select(cls=discord.ui.RoleSelect, placeholder="料金を設定するロールを選択してください")
    async def select_role(self, interaction: discord.Interaction, select: discord.ui.RoleSelect):
        role = select.values[0]
        embed = info_embed(f"ロール別料金設定: {role.name}", "設定したい項目を選んでください。設定していない項目は通常料金のままになります。")
        await interaction.response.edit_message(embed=embed, view=RoleRatePanelView(role.id, role.name))


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

    @discord.ui.button(label="ロール別料金設定", style=discord.ButtonStyle.success, row=2, custom_id="palvoice_role_rate_set")
    async def role_rate_set(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = info_embed("ロールを選択してください", "固定料金を設定したいロールを選んでください。")
        await interaction.response.send_message(embed=embed, view=RoleSelectForRateView(), ephemeral=True)

    @discord.ui.button(label="ロール別料金確認", style=discord.ButtonStyle.secondary, row=2, custom_id="palvoice_role_rate_check")
    async def role_rate_check(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db
        rows = await db.list_role_rates(interaction.guild_id)
        set_rows = [r for r in rows if any(r[c] is not None for c in RATE_LABELS.keys())]
        if not set_rows:
            await interaction.response.send_message(embed=info_embed("ロール別料金", "現在、ロール別の固定料金は設定されていません。"), ephemeral=True)
            return
        embed = info_embed("ロール別料金一覧")
        for row in set_rows:
            lines = [f"{RATE_LABELS[c]}: {row[c]:,} PAL" for c in RATE_LABELS.keys() if row[c] is not None]
            embed.add_field(name=f"<@&{row['role_id']}>", value="\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
