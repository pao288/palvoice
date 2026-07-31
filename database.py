# ===============================================
# database.py
# PAL BANKと同じPostgreSQLデータベースに接続します。
# 「PAL残高」はPAL BANKが作った users テーブルをそのまま使います。
# ===============================================

import asyncpg
import config


class Database:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def connect(self, dsn: str):
        self.pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5)
        await self._init_tables()

    async def close(self):
        if self.pool:
            await self.pool.close()

    async def _init_tables(self):
        async with self.pool.acquire() as conn:
            # PAL BANKと同じ users テーブル(すでにあれば何もしません)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    discord_id BIGINT PRIMARY KEY,
                    username TEXT,
                    pal_balance BIGINT NOT NULL DEFAULT 0,
                    chip_balance BIGINT NOT NULL DEFAULT 0,
                    loan_balance BIGINT NOT NULL DEFAULT 0,
                    account_opened BOOLEAN NOT NULL DEFAULT FALSE,
                    total_sent BIGINT NOT NULL DEFAULT 0,
                    total_received BIGINT NOT NULL DEFAULT 0,
                    total_borrowed BIGINT NOT NULL DEFAULT 0,
                    total_repaid BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                );
            """)

            # PAL VOICEのサーバー設定(チャンネルID・料金など)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS voice_settings (
                    guild_id BIGINT PRIMARY KEY,
                    category_id BIGINT,
                    voice_text_channel_id BIGINT,
                    admin_channel_id BIGINT,
                    log_channel_id BIGINT,
                    create_vc_id BIGINT,
                    rate_3 BIGINT NOT NULL DEFAULT 1000,
                    rate_6 BIGINT NOT NULL DEFAULT 2000,
                    rate_8 BIGINT NOT NULL DEFAULT 2500,
                    rate_12 BIGINT NOT NULL DEFAULT 3500,
                    rate_18 BIGINT NOT NULL DEFAULT 5000,
                    rate_24 BIGINT NOT NULL DEFAULT 6500,
                    extend_rate BIGINT NOT NULL DEFAULT 500,
                    monthly_rate BIGINT NOT NULL DEFAULT 15000
                );
            """)

            # 現在動いている一時VC
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS active_vcs (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    owner_id BIGINT NOT NULL,
                    room_type TEXT NOT NULL,
                    duration_hours INTEGER NOT NULL,
                    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL,
                    warned_10min BOOLEAN NOT NULL DEFAULT FALSE,
                    extended_stage INTEGER NOT NULL DEFAULT 0,
                    total_charged BIGINT NOT NULL DEFAULT 0
                );
            """)

            # ロールごとの固定料金(設定されている項目だけ通常料金より優先されます)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS role_rates (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    role_id BIGINT NOT NULL,
                    rate_3 BIGINT,
                    rate_6 BIGINT,
                    rate_8 BIGINT,
                    rate_12 BIGINT,
                    rate_18 BIGINT,
                    rate_24 BIGINT,
                    extend_rate BIGINT,
                    monthly_rate BIGINT,
                    UNIQUE(guild_id, role_id)
                );
            """)

            # 指定個室の1か月プラン(通常のVCとは別管理・期限のみで削除)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS monthly_rooms (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    owner_id BIGINT NOT NULL,
                    designated_user_id BIGINT NOT NULL,
                    purchased_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL
                );
            """)

    # ---------- guild設定 ----------
    async def ensure_guild_settings(self, guild_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO voice_settings (guild_id)
                VALUES ($1) ON CONFLICT (guild_id) DO NOTHING;
            """, guild_id)

    async def get_guild_settings(self, guild_id: int):
        await self.ensure_guild_settings(guild_id)
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM voice_settings WHERE guild_id=$1;", guild_id)

    async def update_guild_settings(self, guild_id: int, **kwargs):
        if not kwargs:
            return
        await self.ensure_guild_settings(guild_id)
        columns = list(kwargs.keys())
        values = list(kwargs.values())
        set_clause = ", ".join(f"{col}=${i+2}" for i, col in enumerate(columns))
        query = f"UPDATE voice_settings SET {set_clause} WHERE guild_id=$1;"
        async with self.pool.acquire() as conn:
            await conn.execute(query, guild_id, *values)

    async def get_all_guild_settings(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM voice_settings;")

    # ---------- ユーザー残高(PAL BANKのusersテーブルを利用) ----------
    async def ensure_user(self, discord_id: int, username: str):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (discord_id, username)
                VALUES ($1, $2)
                ON CONFLICT (discord_id) DO UPDATE SET username=$2, updated_at=NOW();
            """, discord_id, username)

    async def get_user(self, discord_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM users WHERE discord_id=$1;", discord_id)

    async def try_charge_pal(self, discord_id: int, amount: int) -> bool:
        """残高が足りていれば引き落とし、成功したらTrueを返します。"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                user = await conn.fetchrow(
                    "SELECT pal_balance FROM users WHERE discord_id=$1 FOR UPDATE;", discord_id
                )
                if user is None or user["pal_balance"] < amount:
                    return False
                await conn.execute(
                    "UPDATE users SET pal_balance = pal_balance - $2, updated_at=NOW() WHERE discord_id=$1;",
                    discord_id, amount
                )
                return True

    # ---------- active_vcs ----------
    async def create_active_vc(self, guild_id, channel_id, owner_id, room_type, duration_hours, expires_at, charged):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO active_vcs (guild_id, channel_id, owner_id, room_type, duration_hours, expires_at, total_charged)
                VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id;
            """, guild_id, channel_id, owner_id, room_type, duration_hours, expires_at, charged)
            return row["id"]

    async def get_active_vc_by_channel(self, channel_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM active_vcs WHERE channel_id=$1;", channel_id)

    async def get_active_vc_by_id(self, vc_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM active_vcs WHERE id=$1;", vc_id)

    async def get_all_active_vcs(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM active_vcs;")

    async def update_active_vc(self, vc_id: int, **kwargs):
        if not kwargs:
            return
        columns = list(kwargs.keys())
        values = list(kwargs.values())
        set_clause = ", ".join(f"{col}=${i+2}" for i, col in enumerate(columns))
        query = f"UPDATE active_vcs SET {set_clause} WHERE id=$1;"
        async with self.pool.acquire() as conn:
            await conn.execute(query, vc_id, *values)

    async def delete_active_vc(self, vc_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM active_vcs WHERE id=$1;", vc_id)

    # ---------- role_rates(ロール別固定料金) ----------
    async def ensure_role_rate(self, guild_id: int, role_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO role_rates (guild_id, role_id) VALUES ($1,$2)
                ON CONFLICT (guild_id, role_id) DO NOTHING;
            """, guild_id, role_id)

    async def get_role_rate(self, guild_id: int, role_id: int):
        await self.ensure_role_rate(guild_id, role_id)
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("SELECT * FROM role_rates WHERE guild_id=$1 AND role_id=$2;", guild_id, role_id)

    async def update_role_rate(self, guild_id: int, role_id: int, **kwargs):
        if not kwargs:
            return
        await self.ensure_role_rate(guild_id, role_id)
        columns = list(kwargs.keys())
        values = list(kwargs.values())
        set_clause = ", ".join(f"{col}=${i+3}" for i, col in enumerate(columns))
        async with self.pool.acquire() as conn:
            await conn.execute(
                f"UPDATE role_rates SET {set_clause} WHERE guild_id=$1 AND role_id=$2;",
                guild_id, role_id, *values
            )

    async def get_role_rates_for_roles(self, guild_id: int, role_ids: list):
        if not role_ids:
            return []
        async with self.pool.acquire() as conn:
            return await conn.fetch(
                "SELECT * FROM role_rates WHERE guild_id=$1 AND role_id = ANY($2::bigint[]);", guild_id, role_ids
            )

    async def list_role_rates(self, guild_id: int):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM role_rates WHERE guild_id=$1;", guild_id)

    async def delete_role_rate(self, guild_id: int, role_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM role_rates WHERE guild_id=$1 AND role_id=$2;", guild_id, role_id)

    # ---------- monthly_rooms ----------
    async def create_monthly_room(self, guild_id, channel_id, owner_id, designated_user_id, expires_at):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO monthly_rooms (guild_id, channel_id, owner_id, designated_user_id, expires_at)
                VALUES ($1,$2,$3,$4,$5) RETURNING id;
            """, guild_id, channel_id, owner_id, designated_user_id, expires_at)
            return row["id"]

    async def get_all_monthly_rooms(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch("SELECT * FROM monthly_rooms;")

    async def delete_monthly_room(self, room_id: int):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM monthly_rooms WHERE id=$1;", room_id)
