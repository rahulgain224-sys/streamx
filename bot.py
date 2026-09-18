import sqlite3
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = "8352992151:AAE2Y6soETifFAjizXsPBblj2vff00-exkQ"

ADMIN_ID = 6235831075

DATABASE = "content.db"

# Hosting করার পর এখানে তোমার public HTTPS URL বসাবে
# Example:
# WEB_APP_URL = "https://streamx-video.onrender.com"
WEB_APP_URL = "https://streamx-u24j.onrender.com"


CATEGORIES = {
    "bangla": "🇧🇩 Bangla",
    "english": "🇬🇧 English",
    "viral": "🔥 Viral",
    "trending": "📈 Trending",
}


# =========================================================
# DATABASE
# =========================================================

def db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            thumbnail_file_id TEXT,
            video_file_id TEXT NOT NULL,
            ad_url TEXT,
            created_at TEXT NOT NULL
        )
    """)

    columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(contents)"
        ).fetchall()
    ]

    if "ad_url" not in columns:

        conn.execute(
            "ALTER TABLE contents ADD COLUMN ad_url TEXT"
        )

    conn.commit()
    conn.close()


def add_content(
    category,
    title,
    thumbnail_file_id,
    video_file_id,
    ad_url
):

    conn = db()

    cur = conn.execute(
        """
        INSERT INTO contents
        (
            category,
            title,
            thumbnail_file_id,
            video_file_id,
            ad_url,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            category,
            title,
            thumbnail_file_id,
            video_file_id,
            ad_url,
            datetime.utcnow().isoformat(),
        )
    )

    content_id = cur.lastrowid

    conn.commit()
    conn.close()

    return content_id


def get_content(content_id):

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM contents
        WHERE id = ?
        """,
        (content_id,)
    ).fetchone()

    conn.close()

    return row


def get_category_contents(category):

    conn = db()

    rows = conn.execute(
        """
        SELECT *
        FROM contents
        WHERE category = ?
        ORDER BY id DESC
        """,
        (category,)
    ).fetchall()

    conn.close()

    return rows


# =========================================================
# CATEGORY MENU
# =========================================================

def category_keyboard():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🇧🇩 Bangla",
                callback_data="cat_bangla"
            ),
            InlineKeyboardButton(
                "🇬🇧 English",
                callback_data="cat_english"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔥 Viral",
                callback_data="cat_viral"
            ),
            InlineKeyboardButton(
                "📈 Trending",
                callback_data="cat_trending"
            ),
        ]
    ])


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Web page থেকে ফেরত আসা video token
    if context.args:

        payload = context.args[0]

        if payload.startswith("video_"):

            token = payload[6:]

            await send_unlocked_video(
                update,
                token
            )

            return

    await update.message.reply_text(
        "🎬 Welcome to StreamX!\n\n"
        "Choose a category:",
        reply_markup=category_keyboard()
    )


# =========================================================
# CATEGORY
# =========================================================

async def category_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    category = query.data.replace(
        "cat_",
        "",
        1
    )

    rows = get_category_contents(
        category
    )

    if not rows:

        await query.message.reply_text(
            f"😔 No videos found in "
            f"{CATEGORIES.get(category, category)}."
        )

        return

    await query.message.reply_text(
        f"{CATEGORIES.get(category, category)}\n\n"
        "Select a video:"
    )

    for row in rows:

        title = row["title"]

        thumbnail = row["thumbnail_file_id"]

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "▶️ OPEN VIDEO",
                    callback_data=f"open_video_{row['id']}"
                )
            ]
        ])

        if thumbnail:

            try:

                await query.message.reply_photo(
                    photo=thumbnail,
                    caption=f"🎬 {title}",
                    reply_markup=keyboard
                )

                continue

            except Exception:

                pass

        await query.message.reply_text(
            f"🎬 {title}",
            reply_markup=keyboard
        )


# =========================================================
# OPEN VIDEO
# =========================================================

async def open_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    try:

        content_id = int(
            query.data.replace(
                "open_video_",
                "",
                1
            )
        )

    except ValueError:

        await query.message.reply_text(
            "❌ Invalid video."
        )

        return

    row = get_content(
        content_id
    )

    if not row:

        await query.message.reply_text(
            "❌ Video not found."
        )

        return

    ad_url = (
        row["ad_url"] or ""
    ).strip()

    # =====================================================
    # AD PAGE
    # =====================================================

    if (
        ad_url
        and WEB_APP_URL.startswith("https://")
        and "YOUR-DOMAIN-HERE" not in WEB_APP_URL
    ):

        watch_url = (
            WEB_APP_URL.rstrip("/")
            + f"/watch/{content_id}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📢 WATCH AD & UNLOCK",
                    url=watch_url
                )
            ]
        ])

        await query.message.reply_text(
            f"🎬 {row['title']}\n\n"
            "🔒 Advertisement required.\n\n"
            "Click the button below to open "
            "the advertisement page.",
            reply_markup=keyboard
        )

        return

    # =====================================================
    # NO AD
    # =====================================================

    if not ad_url:

        await query.message.reply_text(
            "⚠️ Advertisement is not configured "
            "for this video yet."
        )

        return

    # =====================================================
    # WEB URL NOT CONFIGURED
    # =====================================================

    await query.message.reply_text(
        "⚠️ Video website is not configured.\n\n"
        "Admin: set WEB_APP_URL in bot.py."
    )


# =========================================================
# SEND UNLOCKED VIDEO
# =========================================================

async def send_unlocked_video(
    update: Update,
    token: str
):

    conn = db()

    row = conn.execute(
        """
        SELECT
            ad_tokens.token,
            ad_tokens.content_id,
            ad_tokens.ad_clicked,
            ad_tokens.unlocked,
            ad_tokens.expires_at,
            ad_tokens.used,
            contents.title

        FROM ad_tokens

        JOIN contents
        ON contents.id = ad_tokens.content_id

        WHERE ad_tokens.token = ?
        """,
        (token,)
    ).fetchone()

    if not row:

        conn.close()

        await update.message.reply_text(
            "❌ Invalid or expired video link."
        )

        return

    now = datetime.utcnow().timestamp()

    try:

        expires_at = float(
            row["expires_at"]
        )

    except Exception:

        expires_at = 0

    # =====================================================
    # USED
    # =====================================================

    if row["used"]:

        conn.close()

        await update.message.reply_text(
            "⚠️ This video link has already been used."
        )

        return

    # =====================================================
    # EXPIRED
    # =====================================================

    if expires_at < now:

        conn.close()

        await update.message.reply_text(
            "⏰ This session has expired.\n\n"
            "Please select the video again."
        )

        return

    # =====================================================
    # NOT UNLOCKED
    # =====================================================

    if not row["ad_clicked"] or not row["unlocked"]:

        conn.close()

        await update.message.reply_text(
            "🔒 Advertisement step is not completed."
        )

        return

    # =====================================================
    # ONE TIME TOKEN
    # =====================================================

    conn.execute(
        """
        UPDATE ad_tokens
        SET used = 1
        WHERE token = ?
        """,
        (token,)
    )

    conn.commit()

    conn.close()

    # =====================================================
    # VIDEO PLAYER PAGE
    # =====================================================

    player_url = (
        WEB_APP_URL.rstrip("/")
        + f"/video/{token}"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "▶️ WATCH VIDEO",
                url=player_url
            )
        ]
    ])

    await update.message.reply_text(
        f"✅ Unlocked!\n\n"
        f"🎬 {row['title']}\n\n"
        "Open the video player:",
        reply_markup=keyboard
    )


# =========================================================
# ADMIN ADD
# =========================================================

async def add_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "⛔ You are not allowed to use /add."
        )

        return

    context.user_data["add_step"] = "category"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🇧🇩 Bangla",
                callback_data="addcat_bangla"
            ),
            InlineKeyboardButton(
                "🇬🇧 English",
                callback_data="addcat_english"
            )
        ],
        [
            InlineKeyboardButton(
                "🔥 Viral",
                callback_data="addcat_viral"
            ),
            InlineKeyboardButton(
                "📈 Trending",
                callback_data="addcat_trending"
            )
        ]
    ])

    await update.message.reply_text(
        "➕ Add New Video\n\n"
        "Choose category:",
        reply_markup=keyboard
    )


# =========================================================
# ADMIN CATEGORY
# =========================================================

async def admin_category_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.from_user.id != ADMIN_ID:

        await query.message.reply_text(
            "⛔ Not allowed."
        )

        return

    category = query.data.replace(
        "addcat_",
        "",
        1
    )

    context.user_data["add_category"] = category

    context.user_data["add_step"] = "title"

    await query.message.reply_text(
        "1️⃣ Send the video title:"
    )


# =========================================================
# ADMIN MESSAGE HANDLER
# =========================================================

async def admin_message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:

        return

    step = context.user_data.get(
        "add_step"
    )

    # =====================================================
    # TITLE
    # =====================================================

    if step == "title":

        if not update.message.text:

            await update.message.reply_text(
                "❌ Please send title as text."
            )

            return

        context.user_data["add_title"] = (
            update.message.text.strip()
        )

        context.user_data["add_step"] = (
            "thumbnail"
        )

        await update.message.reply_text(
            "2️⃣ Send thumbnail image.\n\n"
            "If you don't want thumbnail, send /skip"
        )

        return

    # =====================================================
    # THUMBNAIL
    # =====================================================

    if step == "thumbnail":

        if (
            update.message.text
            and update.message.text.strip().lower()
            == "/skip"
        ):

            context.user_data["add_thumbnail"] = None

            context.user_data["add_step"] = "video"

            await update.message.reply_text(
                "3️⃣ Now forward/send the video "
                "from your private channel."
            )

            return

        if update.message.photo:

            context.user_data["add_thumbnail"] = (
                update.message.photo[-1].file_id
            )

            context.user_data["add_step"] = "video"

            await update.message.reply_text(
                "3️⃣ Now forward/send the video "
                "from your private channel."
            )

            return

        await update.message.reply_text(
            "❌ Send a photo or /skip."
        )

        return

    # =====================================================
    # VIDEO
    # =====================================================

    if step == "video":

        if not update.message.video:

            await update.message.reply_text(
                "❌ Please send/forward a video."
            )

            return

        context.user_data["add_video"] = (
            update.message.video.file_id
        )

        context.user_data["add_step"] = "ad"

        await update.message.reply_text(
            "4️⃣ Send the Adsterra SmartLink URL.\n\n"
            "Example:\n"
            "https://example.com/xxxxx"
        )

        return

    # =====================================================
    # AD URL
    # =====================================================

    if step == "ad":

        if not update.message.text:

            await update.message.reply_text(
                "❌ Send the Adsterra SmartLink URL."
            )

            return

        ad_url = (
            update.message.text.strip()
        )

        if not (
            ad_url.startswith("http://")
            or ad_url.startswith("https://")
        ):

            await update.message.reply_text(
                "❌ Invalid URL."
            )

            return

        category = context.user_data[
            "add_category"
        ]

        title = context.user_data[
            "add_title"
        ]

        thumbnail = context.user_data.get(
            "add_thumbnail"
        )

        video = context.user_data[
            "add_video"
        ]

        content_id = add_content(
            category,
            title,
            thumbnail,
            video,
            ad_url
        )

        context.user_data.clear()

        await update.message.reply_text(
            "✅ Video added successfully!\n\n"
            f"🆔 ID: {content_id}\n"
            f"🎬 {title}\n\n"
            "Users will first see the advertisement "
            "page and then the video player."
        )

        return


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id == ADMIN_ID:

        await update.message.reply_text(
            "🎬 StreamX Admin\n\n"
            "/start - User menu\n"
            "/add - Add video"
        )

    else:

        await update.message.reply_text(
            "Use /start to browse videos."
        )


# =========================================================
# MAIN
# =========================================================

def main():

    init_db()

    if BOT_TOKEN == "PASTE_YOUR_NEW_BOT_TOKEN_HERE":

        print(
            "ERROR: Put your new BotFather token "
            "inside BOT_TOKEN."
        )

        return

    print("================================")
    print("STREAMX BOT STARTING")
    print("================================")

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "add",
            add_command
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            category_callback,
            pattern=r"^cat_(bangla|english|viral|trending)$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            open_video,
            pattern=r"^open_video_\d+$"
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            admin_category_callback,
            pattern=r"^addcat_(bangla|english|viral|trending)$"
        )
    )

    application.add_handler(
        MessageHandler(
            filters.ALL & ~filters.COMMAND,
            admin_message_handler
        )
    )

    print("BOT CONNECTED")
    print("Username: @streamx24bot")
    print("Waiting for messages...")

    application.run_polling()


if __name__ == "__main__":
    main()
