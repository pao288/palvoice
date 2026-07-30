import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta

import config
from utils.embeds import success_embed, error_embed, info_embed, main_embed
from utils.logging_helper import send_voice_log


def rate_column(hours: int) -> str:
    return f"rate_{hours}"


class RoomTypeView(discord.ui.View):
    def __init__(self, guild_id: int, owner_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        for key, info in config.ROOM_TYPES.items():
            btn = discord.ui.Button(label=info["label"], style=discord.ButtonStyle.primary)
            btn.callback = self._make_callback(key)
            self.add_item(btn)
        cancel_btn = discord.ui.Button(label="キャンセル", style=discord.ButtonStyle.danger)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    def _make_callback(self, room_type: str):
        async def callback(interaction: discord.Interaction):
            await self._proceed(interaction, room_type)
        return callback

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=info_embed("キャンセルしました"), view=None)

    async def _proceed(self, interaction: discord.Interaction, room_type: str):
        info = config.ROOM_TYPES[room_type]
        if info["lockable"]:
            embed = info_embed("鍵の設定", f"部屋タイプ: {info['label']}\n鍵を付けますか?")
            await interaction.response.edit_message(embed=embed, view=KeyView(self.guild_id, self.owner_id, room_type))
        else:
            await _after_key(interaction, self.guild_id, self.owner_id, room_type, locked=False)


class KeyView(discord.ui.View):
    def __init__(self, guild_id: int, owner_id: int, room_type: str):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.room_type = room_type

    @discord.ui.button(label="鍵なし", style=discord.ButtonStyle.secondary)
    async def no_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _after_key(interaction, self.guild_id, self.owner_id, self.room_type, locked=False)

    @discord.ui.button(label="鍵付き", style=discord.ButtonStyle.primary)
    async def with_key(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _after_key(interaction, self.guild_id, self.owner_id, self.room_type, locked=True)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=info_embed("キャンセルしました"), view=None)


async def _after_key(interaction: discord.Interaction, guild_id: int, owner_id: int, room_type: str, locked: bool):
    if room_type == "designated":
        modal = DesignatedUserModal(guild_id, owner_id, locked)
        await interaction.response.send_modal(modal)
    else:
        embed = info_embed("利用時間を選択", "利用したい時間を選んでください。")
        await interaction.response.edit_message(
            embed=embed, view=DurationView(guild_id, owner_id, room_type, locked, None)
        )


class DesignatedUserModal(discord.ui.Modal, title="指定個室 - 相手を指定"):
    def __init__(self, guild_id: int, owner_id: int, locked: bool):
        super().__init__()
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.locked = locked
        self.target_input = discord.ui.TextInput(
            label="指定する相手のDiscord ID(数字)",
            placeholder="例: 123456789012345678",
            max_length=25,
        )
        self.add_item(self.target_input)

    async def on_submit(self, interaction: discord.Interaction):
        text = self.target_input.value.strip()
        if not text.isdigit():
            await interaction.response.send_message(embed=error_embed("入力エラー", "Discord IDは数字のみで入力してください。"), ephemeral=True)
            return
        target_id = int(text)

        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message(embed=error_embed("エラー", "サーバー情報が取得できませんでした。"), ephemeral=True)
            return

        if target_id == self.owner_id:
            await interaction.response.send_message(embed=error_embed("エラー", "自分自身は指定できません。"), ephemeral=True)
            return

        target_member = guild.get_member(target_id)
        if target_member is None:
            try:
                target_member = await guild.fetch_member(target_id)
            except discord.NotFound:
                target_member = None

        if target_member is None:
            await interaction.response.send_message(embed=error_embed("エラー", "指定されたIDのメンバーがサーバーに見つかりませんでした。"), ephemeral=True)
            return
        if target_member.bot:
            await interaction.response.send_message(embed=error_embed("エラー", "BOTは指定できません。"), ephemeral=True)
            return

        embed = info_embed(
            "利用プランを選択",
            f"指定した相手: {target_member.mention}\n都度利用にしますか?1か月プランを購入しますか?"
        )
        await interaction.response.send_message(
            embed=embed, view=DesignatedPlanView(self.guild_id, self.owner_id, self.locked, target_id)
        )


class DesignatedPlanView(discord.ui.View):
    def __init__(self, guild_id: int, owner_id: int, locked: bool, target_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.owner_id = owner_id
        self.locked = locked
        self.target_id = target_id

    @discord.ui.button(label="都度利用", style=discord.ButtonStyle.secondary)
    async def per_use(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = info_embed("利用時間を選択", "利用したい時間を選んでください。")
        await interaction.response.edit_message(
            embed=embed, view=DurationView(self.guild_id, self.owner_id, "designated", self.locked, self.target_id)
        )

    @discord.ui.button(label="1か月プラン購入", style=discord.ButtonStyle.primary)
    async def monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        db = interaction.client.db
        settings = await db.get_guild_settings(self.guild_id)
        price = settings["monthly_rate"]

        async def do_purchase(confirm_interaction: discord.Interaction):
            await _create_monthly_room(confirm_interaction.client, self.guild_id, self.owner_id, self.target_id, price, confirm_interaction)

        embed = info_embed(
            "1か月プラン購入の確認",
            f"料金: {price:,} PAL\n有効期間: 30日間\n\nこの内容で購入しますか?"
        )
        await interaction.response.edit_message(embed=embed, view=ConfirmView(do_purchase))

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=info_embed("キャンセルしました"), view=None)


class DurationView(discord.ui.View):
    def __init__(self, guild_id: int, owner_id: int, room_type: str, locked: bool, target_id: int | None):
        super().__init__(timeout=300)
        for hours in config.DURATION_HOURS:
            btn = discord.ui.Button(label=f"{hours}時間", style=discord.ButtonStyle.secondary)
            btn.callback = self._make_callback(guild_id, owner_id, room_type, locked, target_id, hours)
            self.add_item(btn)
        cancel_btn = discord.ui.Button(label="キャンセル", style=discord.ButtonStyle.danger)
        cancel_btn.callback = self._cancel
        self.add_item(cancel_btn)

    def _make_callback(self, guild_id, owner_id, room_type, locked, target_id, hours):
        async def callback(interaction: discord.Interaction):
            await self._proceed(interaction, guild_id, owner_id, room_type, locked, target_id, hours)
        return callback

    async def _cancel(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=info_embed("キャンセルしました"), view=None)

    async def _proceed(self, interaction, guild_id, owner_id, room_type, locked, target_id, hours):
        db = interaction.client.db
        settings = await db.get_guild_settings(guild_id)
        price = settings[rate_column(hours)]
        room_label = config.ROOM_TYPES[room_type]["label"]
        key_label = "鍵付き" if locked else "鍵なし"

        async def do_create(confirm_interaction: discord.Interaction):
            await _create_timed_vc(
                confirm_interaction.client, guild_id, owner_id, room_type, locked, target_id, hours, price, confirm_interaction
            )

        embed = info_embed(
            "VC作成内容の確認",
            f"部屋タイプ: {room_label}\n鍵: {key_label}\n利用時間: {hours}時間\n料金: {price:,} PAL\n\nこの内容で作成しますか?"
        )
        await interaction.response.edit_message(embed=embed, view=ConfirmView(do_create))


class ConfirmView(discord.ui.View):
    def __init__(self, handler, *, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.handler = handler

    @discord.ui.button(label="✅ 実行する", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handler(interaction)

    @discord.ui.button(label="❌ キャンセル", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=info_embed("キャンセルしました"), view=None)


async def _build_overwrites(guild: discord.Guild, owner: discord.Member, locked: bool, target_member: discord.Member | None):
    everyone = guild.default_role
    overwrites = {}

    if locked:
        overwrites[everyone] = discord.PermissionOverwrite(view_channel=False, connect=False)
        overwrites[owner] = discord.PermissionOverwrite(view_channel=True, connect=True)
        if target_member is not None:
            overwrites[target_member] = discord.PermissionOverwrite(view_channel=True, connect=True)
        for member in guild.members:
            if member.bot:
                overwrites[member] = discord.PermissionOverwrite(view_channel=True, connect=True)
    else:
        overwrites[owner] = discord.PermissionOverwrite(view_channel=True, connect=True)

    return overwrites


async def _create_timed_vc(bot, guild_id, owner_id, room_type, locked, target_id, hours, price, interaction):
    db = bot.db
    guild = bot.get_guild(guild_id)
    if guild is None:
        await interaction.response.edit_message(embed=error_embed("エラー", "サーバー情報が取得できませんでした。"), view=None)
        return

    owner = guild.get_member(owner_id)
    if owner is None:
        await interaction.response.edit_message(embed=error_embed("エラー", "メンバー情報が取得できませんでした。"), view=None)
        return

    await db.ensure_user(owner_id, str(owner))
    user = await db.get_user(owner_id)
    if user is None or user["pal_balance"] < price:
        await interaction.response.edit_message(
            embed=error_embed("残高不足", f"PAL残高が不足しているため作成できません。(必要: {price:,} PAL)"), view=None
        )
        return

    ok = await db.try_charge_pal(owner_id, price)
    if not ok:
        await interaction.response.edit_message(embed=error_embed("残高不足", "PAL残高が不足しているため作成できません。"), view=None)
        return

    settings = await db.get_guild_settings(guild_id)
    category = guild.get_channel(settings["category_id"])

    target_member = guild.get_member(target_id) if target_id else None
    overwrites = await _build_overwrites(guild, owner, locked, target_member)

    room_label = config.ROOM_TYPES[room_type]["label"]
    limit = config.ROOM_TYPES[room_type]["limit"]
    channel_name = f"{'🔒' if locked else '🔊'}｜{room_label}｜{owner.display_name}"[:100]

    new_channel = await guild.create_voice_channel(
        channel_name, category=category, overwrites=overwrites, user_limit=limit
    )

    expires_at = datetime.utcnow() + timedelta(hours=hours)
    await db.create_active_vc(guild_id, new_channel.id, owner_id, room_type, hours, expires_at, price)

    try:
        if owner.voice and owner.voice.channel and owner.voice.channel.id == settings["create_vc_id"]:
            await owner.move_to(new_channel)
    except discord.HTTPException:
        pass

    await interaction.response.edit_message(
        embed=success_embed("VCを作成しました", f"{new_channel.mention}\n利用時間: {hours}時間\n料金: {price:,} PAL"),
        view=None,
    )

    await send_voice_log(
        bot, guild_id, "VC作成", owner_id, target_id=target_id,
        amount=price, detail=f"部屋タイプ: {room_label} / 鍵: {'あり' if locked else 'なし'} / 利用時間: {hours}時間"
    )


async def _create_monthly_room(bot, guild_id, owner_id, target_id, price, interaction):
    db = bot.db
    guild = bot.get_guild(guild_id)
    if guild is None:
        await interaction.response.edit_message(embed=error_embed("エラー", "サーバー情報が取得できませんでした。"), view=None)
        return

    owner = guild.get_member(owner_id)
    target_member = guild.get_member(target_id)
    if owner is None or target_member is None:
        await interaction.response.edit_message(embed=error_embed("エラー", "メンバー情報が取得できませんでした。"), view=None)
        return

    await db.ensure_user(owner_id, str(owner))
    user = await db.get_user(owner_id)
    if user is None or user["pal_balance"] < price:
        await interaction.response.edit_message(embed=error_embed("残高不足", f"PAL残高が不足しています。(必要: {price:,} PAL)"), view=None)
        return

    ok = await db.try_charge_pal(owner_id, price)
    if not ok:
        await interaction.response.edit_message(embed=error_embed("残高不足", "PAL残高が不足しています。"), view=None)
        return

    settings = await db.get_guild_settings(guild_id)
    category = guild.get_channel(settings["category_id"])
    overwrites = await _build_overwrites(guild, owner, True, target_member)

    channel_name = f"🔒｜指定個室(月額)｜{owner.display_name}"[:100]
    new_channel = await guild.create_voice_channel(
        channel_name, category=category, overwrites=overwrites, user_limit=2
    )

    expires_at = datetime.utcnow() + timedelta(days=30)
    await db.create_monthly_room(guild_id, new_channel.id, owner_id, target_id, expires_at)

    try:
        if owner.voice and owner.voice.channel and owner.voice.channel.id == settings["create_vc_id"]:
            await owner.move_to(new_channel)
    except discord.HTTPException:
        pass

    await interaction.response.edit_message(
        embed=success_embed("1か月プランを購入しました", f"{new_channel.mention}\n有効期限: 30日間\n料金: {price:,} PAL"),
        view=None,
    )

    await send_voice_log(bot, guild_id, "指定個室1か月プラン購入", owner_id, target_id=target_id, amount=price)


class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_vcs.start()

    def cog_unload(self):
        self.check_vcs.cancel()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        db = self.bot.db

        if after.channel is not None and (before.channel is None or before.channel.id != after.channel.id):
            settings = await db.get_guild_settings(member.guild.id)
            if settings["create_vc_id"] and after.channel.id == settings["create_vc_id"]:
                await db.ensure_user(member.id, str(member))
                embed = main_embed("🎤 VC作成", "部屋タイプを選んでください。")
                try:
                    await member.send(embed=embed, view=RoomTypeView(member.guild.id, member.id))
                except discord.Forbidden:
                    voice_channel = self.bot.get_channel(settings["voice_text_channel_id"])
                    if voice_channel:
                        await voice_channel.send(
                            embed=error_embed(
                                "DMを送信できませんでした",
                                f"{member.mention} DMを受け取れる設定にしてから、もう一度「➕｜VCを作成」に参加してください。"
                            )
                        )

        if before.channel is not None and (after.channel is None or after.channel.id != before.channel.id):
            vc_row = await db.get_active_vc_by_channel(before.channel.id)
            if vc_row is not None:
                remaining = [m for m in before.channel.members if not m.bot]
                if len(remaining) == 0:
                    await self._finalize_vc(vc_row, before.channel, "全員退出")

    async def _finalize_vc(self, vc_row, channel, reason: str):
        db = self.bot.db
        await db.delete_active_vc(vc_row["id"])
        if channel is not None:
            try:
                await channel.delete()
            except discord.HTTPException:
                pass

        duration_text = f"{vc_row['duration_hours']}時間プラン"
        await send_voice_log(
            self.bot, vc_row["guild_id"], "VC終了", vc_row["owner_id"],
            amount=vc_row["total_charged"],
            detail=f"終了理由: {reason} / {duration_text} / 合計請求額: {vc_row['total_charged']:,} PAL"
        )

    @tasks.loop(seconds=config.CHECK_INTERVAL_SECONDS)
    async def check_vcs(self):
        db = self.bot.db
        now = datetime.utcnow()

        active_vcs = await db.get_all_active_vcs()
        for row in active_vcs:
            channel = self.bot.get_channel(row["channel_id"])
            if channel is None:
                await db.delete_active_vc(row["id"])
                continue

            expires_at = row["expires_at"]
            warn_at = expires_at - timedelta(minutes=config.WARNING_MINUTES_BEFORE)

            if not row["warned_10min"] and warn_at <= now < expires_at:
                try:
                    await channel.send(embed=info_embed("⏰ まもなく終了します", "このVCはあと10分で終了予定です。"))
                except discord.HTTPException:
                    pass
                await db.update_active_vc(row["id"], warned_10min=True)
                continue

            if now < expires_at:
                continue

            settings = await db.get_guild_settings(row["guild_id"])

            if row["extended_stage"] == 0:
                ok = await db.try_charge_pal(row["owner_id"], settings["extend_rate"])
                if not ok:
                    await self._finalize_vc(row, channel, "残高不足のため延長できず終了")
                    continue
                new_expires = expires_at + timedelta(minutes=config.EXTEND_GRACE_MINUTES)
                await db.update_active_vc(
                    row["id"], extended_stage=1, expires_at=new_expires,
                    total_charged=row["total_charged"] + settings["extend_rate"]
                )
                try:
                    await channel.send(embed=info_embed(
                        "⏰ 延長料金が発生しました",
                        f"利用時間を超えたため、30分延長料金 {settings['extend_rate']:,} PAL が請求されました。"
                    ))
                except discord.HTTPException:
                    pass
                await send_voice_log(
                    self.bot, row["guild_id"], "延長料金発生", row["owner_id"], amount=settings["extend_rate"]
                )
                continue

            next_hours = config.NEXT_DURATION.get(row["duration_hours"])
            if next_hours is None:
                await self._finalize_vc(row, channel, "24時間経過のため強制終了")
                continue

            current_price = settings[rate_column(row["duration_hours"])]
            next_price = settings[rate_column(next_hours)]
            diff = max(next_price - current_price, 0)

            if diff > 0:
                ok = await db.try_charge_pal(row["owner_id"], diff)
                if not ok:
                    await self._finalize_vc(row, channel, "残高不足のためプラン変更できず終了")
                    continue

            new_expires = row["started_at"] + timedelta(hours=next_hours)
            await db.update_active_vc(
                row["id"], duration_hours=next_hours, extended_stage=0,
                expires_at=new_expires, warned_10min=False,
                total_charged=row["total_charged"] + diff
            )
            try:
                await channel.send(embed=info_embed(
                    "🔄 プランが自動変更されました",
                    f"利用時間を超えたため、{next_hours}時間プランへ自動変更されました。(追加料金 {diff:,} PAL)"
                ))
            except discord.HTTPException:
                pass
            await send_voice_log(
                self.bot, row["guild_id"], "プラン自動変更", row["owner_id"], amount=diff,
                detail=f"{row['duration_hours']}時間 → {next_hours}時間"
            )

        monthly_rooms = await db.get_all_monthly_rooms()
        for room in monthly_rooms:
            if now < room["expires_at"]:
                continue
            channel = self.bot.get_channel(room["channel_id"])
            await db.delete_monthly_room(room["id"])
            if channel is not None:
                try:
                    await channel.delete()
                except discord.HTTPException:
                    pass
            await send_voice_log(
                self.bot, room["guild_id"], "指定個室1か月プラン 期限切れ削除", room["owner_id"],
                target_id=room["designated_user_id"]
            )

    @check_vcs.before_loop
    async def before_check_vcs(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCog(bot))
