class CheckoutView(discord.ui.View):
    def __init__(self, vc_id: int):
        super().__init__(timeout=None)
        self.vc_id = vc_id
        btn = discord.ui.Button(label="🚪 チェックアウト", style=discord.ButtonStyle.danger, custom_id=f"palvoice_checkout_{vc_id}")
        btn.callback = self._checkout
        self.add_item(btn)

    async def _checkout(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        db = interaction.client.db
        row = await db.get_active_vc_by_id(self.vc_id)
        if row is None:
            await interaction.followup.send(embed=error_embed("エラー", "このVC情報が見つかりませんでした。"), ephemeral=True)
            return

        is_owner = interaction.user.id == row["owner_id"]
        is_admin_user = interaction.user.guild_permissions.administrator
        if not (is_owner or is_admin_user):
            await interaction.followup.send(embed=error_embed("権限エラー", "チェックアウトできるのは作成者か管理者のみです。"), ephemeral=True)
            return

        refund = await _calculate_refund(row)
        embed = info_embed(
            "チェックアウトの確認",
            f"未使用分として {refund:,} PAL が返金されます。\nこのVCを終了しますか?"
        )

        async def do_checkout(confirm_interaction: discord.Interaction):
            await confirm_interaction.response.defer()
            latest = await db.get_active_vc_by_id(self.vc_id)
            if latest is None:
                await confirm_interaction.edit_original_response(embed=error_embed("エラー", "既に終了しています。"), view=None)
                return
            actual_refund = await _calculate_refund(latest)
            if actual_refund > 0:
                await db.change_pal(latest["owner_id"], actual_refund)
            await db.delete_active_vc(latest["id"])

            channel = confirm_interaction.client.get_channel(latest["channel_id"])
            await confirm_interaction.edit_original_response(
                embed=success_embed("チェックアウトしました", f"{actual_refund:,} PAL を返金しました。まもなくVCが削除されます。"),
                view=None,
            )
            await send_voice_log(
                confirm_interaction.client, latest["guild_id"], "VC終了(チェックアウト)", latest["owner_id"],
                amount=actual_refund,
                detail=f"{latest['duration_hours']}時間プラン / 返金額: {actual_refund:,} PAL"
            )
            if channel is not None:
                try:
                    await channel.delete()
                except discord.HTTPException:
                    pass

        view = discord.ui.View(timeout=120)
        confirm_btn = discord.ui.Button(label="✅ チェックアウトする", style=discord.ButtonStyle.danger)
        confirm_btn.callback = do_checkout
        cancel_btn = discord.ui.Button(label="❌ キャンセル", style=discord.ButtonStyle.secondary)

        async def cancel_cb(cancel_interaction: discord.Interaction):
            await cancel_interaction.response.edit_message(embed=info_embed("キャンセルしました"), view=None)
        cancel_btn.callback = cancel_cb

        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
