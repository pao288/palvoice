# ===============================================
# config.py
# PAL VOICE全体で使う「固定の設定値」です。
# ===============================================

CATEGORY_NAME = "🎤 PAL VOICE"
CHANNEL_VOICE_TEXT = "🎤｜ボイス"
CHANNEL_ADMIN = "👑｜VOICE管理"
CHANNEL_LOG = "📋｜VOICEログ"

# ---- 部屋タイプ ----
# key: 内部で使う名前 / label: 表示名 / limit: 人数上限 / lockable: 鍵付きにできるか
ROOM_TYPES = {
    "private":   {"label": "個室",           "limit": 2,  "lockable": True},
    "designated": {"label": "指定個室",       "limit": 2,  "lockable": True},
    "small":     {"label": "小部屋",          "limit": 5,  "lockable": True},
    "large":     {"label": "大部屋",          "limit": 15, "lockable": False},
    "party":     {"label": "パーティールーム", "limit": 50, "lockable": False},
}

# ---- 利用時間(時間単位) ----
DURATION_HOURS = [3, 6, 8, 12, 18, 24]

# 30分超過後、自動で移行する次のプラン(24時間の次はなし=そのまま強制終了)
NEXT_DURATION = {3: 6, 6: 8, 8: 12, 12: 18, 18: 24, 24: None}

# ---- 初期料金(あとで管理者パネルから変更可能) ----
DEFAULT_RATES = {3: 1000, 6: 2000, 8: 2500, 12: 3500, 18: 5000, 24: 6500}
DEFAULT_EXTEND_RATE = 500       # 30分延長料金の初期値
DEFAULT_MONTHLY_RATE = 15000    # 指定個室1か月プランの初期値

# ---- 通知・延長のタイミング ----
WARNING_MINUTES_BEFORE = 10   # 終了何分前に通知するか
EXTEND_GRACE_MINUTES = 30     # 超過してから強制的にプラン変更するまでの猶予

# ---- 背景タスクのチェック間隔(秒) ----
CHECK_INTERVAL_SECONDS = 60

# ---- Embedカラー(PAL BANKと統一) ----
COLOR_MAIN = 0xFFD700
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245
COLOR_INFO = 0x5865F2
