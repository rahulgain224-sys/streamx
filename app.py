import os
import sqlite3
import secrets
import time

import requests

from flask import (
    Flask,
    redirect,
    request,
    Response,
    abort,
)

# =====================================================
# CONFIG
# =====================================================

app = Flask(__name__)

DATABASE = "content.db"

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

BOT_USERNAME = "streamx24bot"

TOKEN_LIFETIME = 30 * 60

AD_WAIT_SECONDS = 8

# =====================================================
# DATABASE
# =====================================================

def db_connect():

    conn = sqlite3.connect(
        DATABASE,
        timeout=30
    )

    conn.execute(
        "PRAGMA journal_mode=WAL"
    )

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
# GET CONTENT
# =====================================================

def get_content(content_id):

    conn = db_connect()

    row = conn.execute("""
        SELECT
            id,
            title,
            video_file_id,
            ad_url
        FROM content
        WHERE id = ?
    """, (content_id,)).fetchone()

    conn.close()

    return row


# =====================================================
# CREATE ACCESS TOKEN
# =====================================================

def create_token(content_id):

    token = secrets.token_urlsafe(32)

    conn = db_connect()

    conn.execute("""
        INSERT INTO access_tokens
        (
            token,
            content_id,
            ad_clicked,
            used,
            created_at,
            unlocked_at
        )
        VALUES (?, ?, 0, 0, ?, 0)
    """, (
        token,
        content_id,
        int(time.time())
    ))

    conn.commit()
    conn.close()

    return token


# =====================================================
# CHECK TOKEN
# =====================================================

def get_token(token):

    conn = db_connect()

    row = conn.execute("""
        SELECT
            token,
            content_id,
            ad_clicked,
            used,
            created_at,
            unlocked_at
        FROM access_tokens
        WHERE token = ?
    """, (token,)).fetchone()

    conn.close()

    return row


# =====================================================
# WATCH PAGE
# =====================================================

@app.route("/watch/<int:content_id>")
def watch(content_id):

    content = get_content(content_id)

    if not content:
        return "Video not found", 404

    _, title, _, ad_url = content

    if not ad_url:
        return "Advertisement not configured.", 400

    token = create_token(content_id)

    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>{title}</title>

<style>

body {{
    background:#111;
    color:white;
    font-family:Arial,sans-serif;
    text-align:center;
    padding:30px;
}}

.box {{
    max-width:500px;
    margin:auto;
    background:#1d1d1d;
    padding:30px;
    border-radius:15px;
}}

button {{
    border:0;
    border-radius:10px;
    padding:15px 25px;
    font-size:17px;
    cursor:pointer;
}}

.ad {{
    background:#ff9800;
    color:#000;
}}

.continue {{
    background:#28a745;
    color:white;
    opacity:.4;
    pointer-events:none;
}}

.continue.enabled {{
    opacity:1;
    pointer-events:auto;
}}

#timer {{
    margin-top:20px;
    color:#aaa;
}}

</style>
</head>

<body>

<div class="box">

<h2>🎬 {title}</h2>

<p>Video দেখতে advertisement step complete করো.</p>

<a
    href="/ad/{token}"
    target="_blank"
    onclick="startTimer()"
>
    <button class="ad">
        📢 WATCH AD
    </button>
</a>

<p id="timer">
    প্রথমে WATCH AD চাপো
</p>

<br>

<a id="continueLink" href="/unlock/{token}">
    <button id="continueBtn" class="continue">
        ▶️ CONTINUE
    </button>
</a>

</div>

<script>

let started = false;

function startTimer() {{

    if (started) return;

    started = true;

    let seconds = {AD_WAIT_SECONDS};

    const timer = document.getElementById("timer");
    const btn = document.getElementById("continueBtn");

    timer.innerText =
        "Please wait " + seconds + " seconds...";

    const interval = setInterval(function() {{

        seconds--;

        if (seconds > 0) {{

            timer.innerText =
                "Please wait " + seconds + " seconds...";

        }} else {{

            clearInterval(interval);

            timer.innerText =
                "✅ Continue button unlocked";

            btn.classList.add("enabled");

        }}

    }}, 1000);
}}

</script>

</body>
</html>
"""


# =====================================================
# AD REDIRECT
# =====================================================

@app.route("/ad/<token>")
def ad_redirect(token):

    row = get_token(token)

    if not row:
        return "Invalid or expired link.", 404

    (
        token_value,
        content_id,
        ad_clicked,
        used,
        created_at,
        unlocked_at
    ) = row

    if time.time() - created_at > TOKEN_LIFETIME:

        conn = db_connect()

        conn.execute(
            "DELETE FROM access_tokens WHERE token = ?",
            (token,)
        )

        conn.commit()
        conn.close()

        return "⏰ Link expired.", 410

    content = get_content(content_id)

    if not content:
        return "Video not found.", 404

    ad_url = content[3]

    # Record that user clicked our WATCH AD button
    conn = db_connect()

    conn.execute("""
        UPDATE access_tokens
        SET ad_clicked = 1
        WHERE token = ?
    """, (token,))

    conn.commit()
    conn.close()

    return redirect(ad_url)


# =====================================================
# UNLOCK
# =====================================================

@app.route("/unlock/<token>")
def unlock(token):

    row = get_token(token)

    if not row:
        return "Invalid or expired link.", 404

    (
        token_value,
        content_id,
        ad_clicked,
        used,
        created_at,
        unlocked_at
    ) = row

    if time.time() - created_at > TOKEN_LIFETIME:
        return "⏰ Link expired.", 410

    if not ad_clicked:
        return """
        <html>
        <body style="background:#111;color:white;text-align:center;padding:50px;font-family:Arial;">
        <h2>⚠️ Advertisement step incomplete</h2>
        <p>Please go back and click WATCH AD first.</p>
        </body>
        </html>
        """, 403

    # Generate Telegram deep link
    telegram_url = (
        f"https://t.me/{BOT_USERNAME}"
        f"?start=video_{token}"
    )

    return f"""
<!DOCTYPE html>
<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width,initial-scale=1.0">

<title>Video Unlocked</title>

<style>

body {{
    background:#111;
    color:white;
    text-align:center;
    font-family:Arial;
    padding:40px;
}}

.box {{
    max-width:500px;
    margin:auto;
    background:#1d1d1d;
    padding:30px;
    border-radius:15px;
}}

button {{
    background:#28a745;
    color:white;
    border:0;
    padding:15px 25px;
    border-radius:10px;
    font-size:18px;
}}

</style>

</head>

<body>

<div class="box">

<h2>✅ Video Unlocked</h2>

<p>Telegram-এ ফিরে গিয়ে video খুলতে নিচের button চাপো.</p>

<a href="{telegram_url}">
<button>
📲 CONTINUE TO VIDEO
</button>
</a>

</div>

</body>

</html>
"""


# =====================================================
# VIDEO PAGE
# =====================================================

@app.route("/video/<token>")
def video_page(token):

    row = get_token(token)

    if not row:
        return "Invalid or expired link.", 404

    (
        token_value,
        content_id,
        ad_clicked,
        used,
        created_at,
        unlocked_at
    ) = row

    if time.time() - created_at > TOKEN_LIFETIME:
        return "⏰ Video link expired.", 410

    if not ad_clicked:
        return "Advertisement step incomplete.", 403

    content = get_content(content_id)

    if not content:
        return "Video not found.", 404

    title = content[1]

    stream_url = f"/stream/{token}"

    return f"""
<!DOCTYPE html>
<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width,initial-scale=1.0">

<title>{title}</title>

<style>

body {{
    margin:0;
    background:#000;
    color:white;
    font-family:Arial;
}}

.container {{
    max-width:900px;
    margin:auto;
    padding:20px;
}}

video {{
    width:100%;
    max-height:80vh;
    background:#000;
}}

h2 {{
    font-size:20px;
}}

</style>

</head>

<body>

<div class="container">

<h2>🎬 {title}</h2>

<video
    controls
    playsinline
    preload="metadata"
>
    <source
        src="{stream_url}"
        type="video/mp4"
    >

    Your browser does not support video playback.

</video>

</div>

</body>

</html>
"""


# =====================================================
# TELEGRAM FILE INFO
# =====================================================

def telegram_get_file(file_id):

    if not BOT_TOKEN:
        raise Exception("BOT_TOKEN is missing")

    url = (
        f"https://api.telegram.org/bot"
        f"{BOT_TOKEN}/getFile"
    )

    response = requests.get(
        url,
        params={"file_id": file_id},
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise Exception(
            data.get("description", "Telegram API error")
        )

    return data["result"]["file_path"]


# =====================================================
# STREAM TELEGRAM VIDEO
# =====================================================

@app.route("/stream/<token>")
def stream_video(token):

    row = get_token(token)

    if not row:
        abort(404)

    (
        token_value,
        content_id,
        ad_clicked,
        used,
        created_at,
        unlocked_at
    ) = row

    if time.time() - created_at > TOKEN_LIFETIME:
        abort(410)

    if not ad_clicked:
        abort(403)

    content = get_content(content_id)

    if not content:
        abort(404)

    video_file_id = content[2]

    try:

        file_path = telegram_get_file(
            video_file_id
        )

    except Exception as e:

        return (
            f"Telegram file error: {str(e)}",
            500
        )

    telegram_file_url = (
        f"https://api.telegram.org/file/bot"
        f"{BOT_TOKEN}/{file_path}"
    )

    headers = {}

    # Browser video player sends Range requests
    range_header = request.headers.get("Range")

    if range_header:
        headers["Range"] = range_header

    try:

        r = requests.get(
            telegram_file_url,
            headers=headers,
            stream=True,
            timeout=60
        )

    except Exception as e:

        return (
            f"Stream error: {str(e)}",
            500
        )

    response_headers = {}

    for header in [
        "Content-Type",
        "Content-Length",
        "Content-Range",
        "Accept-Ranges",
    ]:

        if header in r.headers:
            response_headers[header] = r.headers[header]

    response_headers["Cache-Control"] = "no-store"

    def generate():

        try:

            for chunk in r.iter_content(
                chunk_size=1024 * 1024
            ):

                if chunk:
                    yield chunk

        finally:

            r.close()

    return Response(
        generate(),
        status=r.status_code,
        headers=response_headers
    )


# =====================================================
# HEALTH CHECK
# =====================================================

@app.route("/")
def home():

    return """
    <html>
    <head>
        <title>StreamX</title>
    </head>

    <body style="
        background:#111;
        color:white;
        text-align:center;
        font-family:Arial;
        padding:50px;
    ">

        <h1>🎬 StreamX</h1>

        <p>Website is running successfully.</p>

    </body>
    </html>
    """


# =====================================================
# INIT
# =====================================================

init_db()


if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", "8080")
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
