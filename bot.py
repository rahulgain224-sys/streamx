import os
import sqlite3
import secrets
import threading
import time
import asyncio

from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# =====================================================
# CONFIG
# =====================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 6235831075

DATABASE = "content.db"

WEB_APP_URL = "https://streamx-u24j.onrender.com"

# =====================================================
# CATEGORIES
# =====================================================

CATEGORIES = {
    "bangla": "🇧🇩 Bangla",
    "english": "🇬🇧 English",
    "viral": "🔥 Viral",
    "trending": "📈 Trending",
}

# =====================================================
# ADD STATES
# =====================================================

ADD_CATEGORY, ADD_TITLE, ADD_THUMBNAIL, ADD_VIDEO, ADD_AD_URL = range(5)

# =====================================================
# DATABASE
# =====================================================

def db_connect():
    conn = sqlite3.connect(DATABASE, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = db_connect()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            thumbnail_file_id TEXT,
            video_file_id TEXT NOT NULL,
            ad_url TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS access_tokens (
            token TEXT PRIMARY KEY,
            content_id INTEGER NOT NULL,
            ad_clicked INTEGER DEFAULT 0,
            used INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL,
            unlocked_at INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# =====================================================
# MAIN MENU
# =====================================================

def category_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🇧🇩 Bangla", callback_data="cat_bangla"),
            InlineKeyboardButton("🇬🇧 English", callback_data="cat_english"),
        ],
        [
            InlineKeyboardButton("🔥 Viral", callback_data="cat_viral"),
            InlineKeyboardButton("📈 Trending", callback_data="cat_trending"),
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    args = context.args

    # -------------------------------------------------
    # VIDEO DEEP LINK
    # -------------------------------------------------

    if args and args[0].startswith("video_"):

        token = args[0][6:]

        conn = db_connect()

        row = conn.execute("""
            SELECT content_id, ad_clicked, used, created_at
            FROM access_tokens
            WHERE token = ?
        """, (token,)).fetchone()

        if not row:
            conn.close()

            await update.message.reply_text(
                "❌ এই video link আর valid নেই।"
            )
            return

        content_id, ad_clicked, used, created_at = row

        # 30 minute expiry
        if time.time() - created_at > 30 * 60:
            conn.execute(
                "DELETE FROM access_tokens WHERE token = ?",
                (token,)
            )
            conn.commit()
            conn.close()

            await update.message.reply_text(
                "⏰ এই video link-এর সময় শেষ হয়ে গেছে।"
            )
            return

        if not ad_clicked:
            conn.close()

            await update.message.reply_text(
                "⚠️ আগে advertisement step complete করো।"
            )
            return

        if used:
            conn.close()

            await update.message.reply_text(
                "⚠️ এই link ইতিমধ্যে ব্যবহার করা হয়েছে।"
            )
            return

        # Mark one-time deep link as used
        conn.execute("""
            UPDATE access_tokens
            SET used = 1,
                unlocked_at = ?
            WHERE token = ?
        """, (int(time.time()), token))

        conn.commit()
        conn.close()

        video_url = (
            WEB_APP_URL.rstrip("/")
            + f"/video/{token}"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "▶️ WATCH VIDEO",
                    url=video_url
                )
            ]
        ])

        await update.message.reply_text(
            "✅ Video unlocked!\n\n"
            "নিচের button চাপলে browser-এ video player খুলবে:",
            reply_markup=keyboard
        )

        return

    # -------------------------------------------------
    # NORMAL START
    # -------------------------------------------------

    await update.message.reply_text(
        "🎬 Welcome to StreamX!\n\n"
        "একটি category নির্বাচন করো:",
        reply_markup=category_keyboard()
    )


# =====================================================
# CATEGORY BUTTON
# =====================================================

async def category_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    category = query.data.replace("cat_", "")

    conn = db_connect()

    rows = conn.execute("""
        SELECT id, title, thumbnail_file_id
        FROM content
        WHERE category = ?
        ORDER BY id DESC
    """, (category,)).fetchall()

    conn.close()

    if not rows:
        await query.edit_message_text(
            f"{CATEGORIES[category]}\n\n"
            "এই category-তে এখনো কোনো video নেই।",
            reply_markup=category_keyboard()
        )
        return

    await query.edit_message_text(
        f"{CATEGORIES[category]}\n\n"
        "নিচের video-গুলো থেকে একটি নির্বাচন করো:"
    )

    for content_id, title, thumbnail in rows:

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "▶️ OPEN VIDEO",
                    callback_data=f"open_{content_id}"
                )
            ]
        ])

        text = f"🎬 {title}"

        try:
            if thumbnail:
                await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=thumbnail,
                    caption=text,
                    reply_markup=keyboard
                )
            else:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=text,
                    reply_markup=keyboard
                )

        except Exception:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=text,
                reply_markup=keyboard
            )


# =====================================================
# OPEN VIDEO
# =====================================================

async def open_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    content_id = int(query.data.replace("open_", ""))

    conn = db_connect()

    row = conn.execute("""
        SELECT title, ad_url
        FROM content
        WHERE id = ?
    """, (content_id,)).fetchone()

    conn.close()

    if not row:
        await query.message.reply_text(
            "❌ Video পাওয়া যায়নি।"
        )
        return

    title, ad_url = row

    if not ad_url:
        await query.message.reply_text(
            "⚠️ এই video-তে advertisement সেট করা হয়নি।"
        )
        return

    if not WEB_APP_URL.startswith("https://"):
        await query.message.reply_text(
            "⚠️ Website URL configure করা হয়নি।"
        )
        return

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
        f"🎬 {title}\n\n"
        "Video দেখতে আগে নিচের button চাপো।\n"
        "Advertisement page খুলবে।",
        reply_markup=keyboard
    )


# =====================================================
# ADMIN: /add
# =====================================================

async def add_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ এই command শুধু admin-এর জন্য।"
        )
        return ConversationHandler.END

    await update.message.reply_text(
        "📂 Video category নির্বাচন করো:",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🇧🇩 Bangla",
                    callback_data="addcat_bangla"
                ),
                InlineKeyboardButton(
                    "🇬🇧 English",
                    callback_data="addcat_english"
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔥 Viral",
                    callback_data="addcat_viral"
                ),
                InlineKeyboardButton(
                    "📈 Trending",
                    callback_data="addcat_trending"
                ),
            ],
        ])
    )

    return ADD_CATEGORY


async def add_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query
    await query.answer()

    category = query.data.replace("addcat_", "")

    context.user_data["add_category"] = category

    await query.message.reply_text(
        "✏️ এখন video-এর title পাঠাও:"
    )

    return ADD_TITLE


async def add_title(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data["add_title"] = update.message.text.strip()

    await update.message.reply_text(
        "🖼️ এখন thumbnail/photo পাঠাও।\n\n"
        "Thumbnail দিতে না চাইলে `/skip` লিখো।"
    )

    return ADD_THUMBNAIL


async def add_thumbnail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.message.text and update.message.text.strip() == "/skip":

        context.user_data["add_thumbnail"] = None

    elif update.message.photo:

        context.user_data["add_thumbnail"] = (
            update.message.photo[-1].file_id
        )

    else:

        await update.message.reply_text(
            "⚠️ একটি photo পাঠাও অথবা `/skip` লিখো।"
        )

        return ADD_THUMBNAIL

    await update.message.reply_text(
        "🎥 এখন video পাঠাও বা তোমার private channel থেকে "
        "video post-টি forward করো।"
    )

    return ADD_VIDEO


async def add_video(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message.video:

        await update.message.reply_text(
            "⚠️ Video message পাঠাও।"
        )

        return ADD_VIDEO

    context.user_data["add_video"] = (
        update.message.video.file_id
    )

    await update.message.reply_text(
        "🔗 এখন Adsterra SmartLink URL পাঠাও:\n\n"
        "উদাহরণ:\n"
        "https://example.com/..."
    )

    return ADD_AD_URL


async def add_ad_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    ad_url = update.message.text.strip()

    if not ad_url.startswith(("http://", "https://")):

        await update.message.reply_text(
            "⚠️ সঠিক URL পাঠাও।"
        )

        return ADD_AD_URL

    category = context.user_data["add_category"]
    title = context.user_data["add_title"]
    thumbnail = context.user_data.get("add_thumbnail")
    video_file_id = context.user_data["add_video"]

    conn = db_connect()

    conn.execute("""
        INSERT INTO content
        (
            category,
            title,
            thumbnail_file_id,
            video_file_id,
            ad_url,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        category,
        title,
        thumbnail,
        video_file_id,
        ad_url,
        int(time.time())
    ))

    conn.commit()
    conn.close()

    context.user_data.clear()

    await update.message.reply_text(
        "✅ Video successfully added!\n\n"
        f"📂 Category: {CATEGORIES[category]}\n"
        f"🎬 Title: {title}"
    )

    return ConversationHandler.END


async def cancel_add(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ Add process cancelled."
    )

    return ConversationHandler.END


# =====================================================
# START FLASK SERVER
# =====================================================

def start_web_server():

    from app import app

    port = int(os.environ.get("PORT", "8080"))

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        use_reloader=False
    )


# =====================================================
# BOT
# =====================================================

def run_bot():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is missing."
        )

    init_db()

    application = Application.builder().token(
        BOT_TOKEN
    ).build()

    # /start
    application.add_handler(
        CommandHandler("start", start)
    )

    # category
    application.add_handler(
        CallbackQueryHandler(
            category_callback,
            pattern=r"^cat_"
        )
    )

    # open video
    application.add_handler(
        CallbackQueryHandler(
            open_video,
            pattern=r"^open_\d+$"
        )
    )

    # add conversation
    add_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_command)
        ],

        states={
            ADD_CATEGORY: [
                CallbackQueryHandler(
                    add_category,
                    pattern=r"^addcat_"
                )
            ],

            ADD_TITLE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_title
                )
            ],

            ADD_THUMBNAIL: [
                MessageHandler(
                    filters.PHOTO | filters.TEXT,
                    add_thumbnail
                )
            ],

            ADD_VIDEO: [
                MessageHandler(
                    filters.VIDEO,
                    add_video
                )
            ],

            ADD_AD_URL: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    add_ad_url
                )
            ],
        },

        fallbacks=[
            CommandHandler("cancel", cancel_add)
        ]
    )

    application.add_handler(add_conversation)

    print("================================")
    print("STREAMX BOT + WEBSITE STARTING")
    print("================================")

    application.run_polling(
        drop_pending_updates=True
    )


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    # Flask website runs in background thread
    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True
    )

    web_thread.start()

    # Telegram bot runs in main thread
    run_bot()
