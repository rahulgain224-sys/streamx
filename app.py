import os
import sqlite3
import secrets
import time

import requests

from flask import (
    Flask,
    request,
    render_template_string,
    redirect,
    abort,
    Response,
)


# =========================================================
# SETTINGS
# =========================================================

DATABASE = "content.db"

BOT_TOKEN = "8352992151:AAE2Y6soETifFAjizXsPBblj2vff00-exkQ"

BOT_USERNAME = "streamx24bot"

PORT = int(
    os.environ.get(
        "PORT",
        "8080"
    )
)

# Token কতক্ষণ valid থাকবে
TOKEN_LIFETIME = 30 * 60

# Ad button click করার পর minimum wait
AD_WAIT_SECONDS = 8


app = Flask(__name__)


# =========================================================
# DATABASE
# =========================================================

def db():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


def ensure_token_table():

    conn = db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ad_tokens (

            token TEXT PRIMARY KEY,

            content_id INTEGER NOT NULL,

            ad_clicked INTEGER DEFAULT 0,

            unlocked INTEGER DEFAULT 0,

            used INTEGER DEFAULT 0,

            created_at REAL NOT NULL,

            expires_at REAL NOT NULL
        )
    """)

    columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(ad_tokens)"
        ).fetchall()
    ]

    if "used" not in columns:

        conn.execute(
            """
            ALTER TABLE ad_tokens
            ADD COLUMN used INTEGER DEFAULT 0
            """
        )

    conn.commit()

    conn.close()


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


def create_token(content_id):

    token = secrets.token_urlsafe(
        32
    )

    now = time.time()

    expires = (
        now
        + TOKEN_LIFETIME
    )

    conn = db()

    conn.execute(
        """
        INSERT INTO ad_tokens
        (
            token,
            content_id,
            ad_clicked,
            unlocked,
            used,
            created_at,
            expires_at
        )

        VALUES (?, ?, 0, 0, 0, ?, ?)
        """,
        (
            token,
            content_id,
            now,
            expires
        )
    )

    conn.commit()

    conn.close()

    return token


def get_token(token):

    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM ad_tokens
        WHERE token = ?
        """,
        (token,)
    ).fetchone()

    conn.close()

    return row


def mark_ad_clicked(token):

    conn = db()

    conn.execute(
        """
        UPDATE ad_tokens
        SET ad_clicked = 1
        WHERE token = ?
        """,
        (token,)
    )

    conn.commit()

    conn.close()


def unlock_token(token):

    conn = db()

    conn.execute(
        """
        UPDATE ad_tokens
        SET unlocked = 1
        WHERE token = ?
        """,
        (token,)
    )

    conn.commit()

    conn.close()


def is_expired(row):

    if not row:
        return True

    return (
        float(row["expires_at"])
        < time.time()
    )


# =========================================================
# ADVERTISEMENT PAGE
# =========================================================

AD_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

<title>
Watch Ad - StreamX
</title>


<style>

body {

    margin: 0;

    min-height: 100vh;

    display: flex;

    justify-content: center;

    align-items: center;

    background: #101114;

    color: white;

    font-family: Arial, sans-serif;

}


.box {

    width: min(92%, 460px);

    background: #1b1d22;

    padding: 28px;

    border-radius: 18px;

    text-align: center;

    box-sizing: border-box;

}


h2 {

    margin-top: 0;

}


.title {

    color: #ddd;

    margin-bottom: 22px;

}


.btn {

    display: block;

    width: 100%;

    padding: 15px;

    margin-top: 12px;

    border: 0;

    border-radius: 10px;

    font-size: 16px;

    font-weight: bold;

    text-decoration: none;

    box-sizing: border-box;

    cursor: pointer;

}


.ad {

    background: #ff8a00;

    color: #111;

}


.continue {

    background: #28a745;

    color: white;

}


.disabled {

    background: #555;

    color: #bbb;

    pointer-events: none;

}


#status {

    margin-top: 16px;

    color: #ffcf66;

    min-height: 20px;

}


.small {

    color: #999;

    font-size: 13px;

    margin-top: 18px;

    line-height: 1.5;

}

</style>

</head>


<body>


<div class="box">

<h2>
📢 Advertisement
</h2>


<div class="title">

🎬 {{ title }}

</div>


<p>

Advertisement খুলে কিছুক্ষণ অপেক্ষা করুন।

</p>


<a
    class="btn ad"
    href="/ad/{{ token }}"
    target="_blank"
    rel="noopener noreferrer"
    onclick="startAdTimer()"
>

📢 WATCH AD

</a>


<a
    id="continueBtn"
    class="btn disabled"
    href="/unlock/{{ token }}"
>

🔒 Continue

</a>


<div id="status">

WATCH AD চাপুন

</div>


<div class="small">

WATCH AD চাপলে Advertisement নতুন tab-এ খুলবে।
<br>
তারপর এই tab-এ ফিরে এসে Continue চাপুন।

</div>


</div>


<script>

let allowContinue = false;

let timerStarted = false;

let remaining = {{ wait_seconds }};


function startAdTimer() {

    if (timerStarted) {

        return;

    }


    timerStarted = true;


    document.getElementById(
        "status"
    ).innerText =
        "Advertisement opened. Please wait "
        + remaining
        + " seconds...";


    const timer = setInterval(
        function() {

            remaining--;


            if (remaining > 0) {

                document.getElementById(
                    "status"
                ).innerText =
                    "Continue available in "
                    + remaining
                    + " seconds...";

            }

            else {

                clearInterval(timer);

                allowContinue = true;


                const btn =
                    document.getElementById(
                        "continueBtn"
                    );


                btn.classList.remove(
                    "disabled"
                );


                btn.style.pointerEvents =
                    "auto";


                btn.style.background =
                    "#28a745";


                document.getElementById(
                    "status"
                ).innerText =
                    "✅ You can continue now.";

            }

        },
        1000
    );

}


document
    .getElementById("continueBtn")
    .addEventListener(
        "click",
        function(event) {

            if (!allowContinue) {

                event.preventDefault();

                return false;

            }

        }
    );

</script>


</body>

</html>

"""


# =========================================================
# UNLOCK PAGE
# =========================================================

DONE_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

<title>
StreamX
</title>


<style>

body {

    margin: 0;

    min-height: 100vh;

    display: flex;

    align-items: center;

    justify-content: center;

    background: #101114;

    color: white;

    font-family: Arial, sans-serif;

}


.box {

    width: min(92%, 460px);

    background: #1b1d22;

    padding: 28px;

    border-radius: 18px;

    text-align: center;

}


a {

    display: block;

    margin-top: 20px;

    padding: 15px;

    border-radius: 10px;

    background: #2481cc;

    color: white;

    text-decoration: none;

    font-weight: bold;

}


.small {

    color: #aaa;

    margin-top: 15px;

    font-size: 13px;

}

</style>

</head>


<body>


<div class="box">


<h2>

✅ Advertisement Complete

</h2>


<p>

এখন ভিডিওটি খুলুন।

</p>


<a href="{{ telegram_url }}">

📲 OPEN VIDEO IN TELEGRAM

</a>


<div class="small">

Telegram খুলে ভিডিওটি Open করুন।

</div>


</div>


</body>

</html>

"""


# =========================================================
# VIDEO PAGE
# =========================================================

VIDEO_PAGE = """

<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width,initial-scale=1"
>

<title>
{{ title }} - StreamX
</title>


<style>

body {

    margin: 0;

    min-height: 100vh;

    background: #08090b;

    color: white;

    font-family: Arial, sans-serif;

}


.wrap {

    max-width: 900px;

    margin: 0 auto;

    padding: 18px;

    box-sizing: border-box;

}


h2 {

    font-size: 20px;

    margin: 5px 0 16px;

}


.player {

    width: 100%;

    background: #000;

    border-radius: 14px;

    overflow: hidden;

}


video {

    width: 100%;

    max-height: 75vh;

    display: block;

    background: #000;

}


.info {

    margin-top: 16px;

    padding: 16px;

    background: #15171b;

    border-radius: 12px;

}


.notice {

    color: #999;

    font-size: 13px;

    line-height: 1.5;

    margin-top: 8px;

}


.back {

    display: inline-block;

    margin-top: 14px;

    color: #7dbbff;

    text-decoration: none;

}

</style>

</head>


<body>


<div class="wrap">


<h2>

🎬 {{ title }}

</h2>


<div class="player">


<video
    controls
    playsinline
    preload="metadata"
    src="/stream/{{ token }}"
>

</video>


</div>


<div class="info">

▶️ StreamX Video Player

<div class="notice">

শুধু নির্বাচিত ভিডিওটি এখানে দেখানো হচ্ছে।

</div>

</div>


<a
    class="back"
    href="https://t.me/{{ bot_username }}"
>

← Back to Telegram

</a>


</div>


</body>

</html>

"""


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return """

    <h2>
    StreamX is running ✅
    </h2>

    <p>
    Telegram Bot: @streamx24bot
    </p>

    """


# =========================================================
# WATCH / AD PAGE
# =========================================================

@app.route(
    "/watch/<int:content_id>"
)
def watch(content_id):

    ensure_token_table()

    content = get_content(
        content_id
    )

    if not content:

        abort(404)

    ad_url = (
        content["ad_url"] or ""
    ).strip()

    if not ad_url:

        return (
            "Advertisement is not configured.",
            400
        )

    token = create_token(
        content_id
    )

    return render_template_string(
        AD_PAGE,
        title=content["title"],
        token=token,
        wait_seconds=AD_WAIT_SECONDS
    )


# =========================================================
# AD REDIRECT
# =========================================================

@app.route(
    "/ad/<token>"
)
def ad_redirect(token):

    ensure_token_table()

    row = get_token(token)

    if not row:

        return (
            "Invalid session.",
            404
        )

    if is_expired(row):

        return (
            "Advertisement session expired.",
            410
        )

    content = get_content(
        row["content_id"]
    )

    if not content:

        abort(404)

    ad_url = (
        content["ad_url"] or ""
    ).strip()

    if not ad_url:

        return (
            "Advertisement URL missing.",
            400
        )

    # WATCH AD button clicked
    mark_ad_clicked(token)

    return redirect(
        ad_url
    )


# =========================================================
# UNLOCK
# =========================================================

@app.route(
    "/unlock/<token>"
)
def unlock(token):

    ensure_token_table()

    row = get_token(token)

    if not row:

        return (
            "Invalid session.",
            404
        )

    if is_expired(row):

        return (
            "Session expired.",
            410
        )

    if not row["ad_clicked"]:

        return (
            "❌ Please click WATCH AD first.",
            403
        )

    unlock_token(
        token
    )

    telegram_url = (
        f"https://t.me/{BOT_USERNAME}"
        f"?start=video_{token}"
    )

    return render_template_string(
        DONE_PAGE,
        telegram_url=telegram_url
    )


# =========================================================
# VIDEO PAGE
# =========================================================

@app.route(
    "/video/<token>"
)
def video_page(token):

    ensure_token_table()

    row = get_token(token)

    if not row:

        return (
            "Invalid video session.",
            404
        )

    if is_expired(row):

        return (
            "Video session expired.",
            410
        )

    if not row["unlocked"]:

        return (
            "🔒 Advertisement step required.",
            403
        )

    content = get_content(
        row["content_id"]
    )

    if not content:

        abort(404)

    return render_template_string(
        VIDEO_PAGE,
        title=content["title"],
        token=token,
        bot_username=BOT_USERNAME
    )


# =========================================================
# GET TELEGRAM FILE URL
# =========================================================

def telegram_file_url(
    file_id
):

    if (
        BOT_TOKEN
        == "PASTE_YOUR_NEW_BOT_TOKEN_HERE"
    ):

        raise RuntimeError(
            "BOT_TOKEN is not configured."
        )

    response = requests.post(

        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/getFile",

        json={
            "file_id": file_id
        },

        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):

        raise RuntimeError(
            data
        )

    file_path = (
        data["result"]["file_path"]
    )

    return (
        f"https://api.telegram.org/"
        f"file/bot{BOT_TOKEN}/"
        f"{file_path}"
    )


# =========================================================
# VIDEO STREAM
# =========================================================

@app.route(
    "/stream/<token>"
)
def stream_video(token):

    ensure_token_table()

    row = get_token(token)

    if not row:

        return (
            "Invalid session.",
            404
        )

    if is_expired(row):

        return (
            "Video session expired.",
            410
        )

    if not row["unlocked"]:

        return (
            "Video locked.",
            403
        )

    content = get_content(
        row["content_id"]
    )

    if not content:

        abort(404)

    try:

        telegram_url = telegram_file_url(
            content["video_file_id"]
        )

    except Exception as error:

        print(
            "Telegram getFile error:",
            error
        )

        return (
            "Could not prepare video.",
            502
        )

    headers = {}

    if request.headers.get(
        "Range"
    ):

        headers["Range"] = (
            request.headers["Range"]
        )

    try:

        upstream = requests.get(

            telegram_url,

            headers=headers,

            stream=True,

            timeout=(
                15,
                120
            )
        )

    except Exception as error:

        print(
            "Video stream error:",
            error
        )

        return (
            "Video stream failed.",
            502
        )

    response_headers = {}

    for key in [

        "Content-Type",
        "Content-Length",
        "Content-Range",
        "Accept-Ranges",
        "ETag",
        "Last-Modified",

    ]:

        value = (
            upstream.headers.get(key)
        )

        if value:

            response_headers[key] = value

    response_headers[
        "Accept-Ranges"
    ] = "bytes"

    return Response(

        upstream.iter_content(
            chunk_size=1024 * 256
        ),

        status=upstream.status_code,

        headers=response_headers,

        direct_passthrough=True
    )


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    ensure_token_table()

    print(
        f"StreamX web server running "
        f"on port {PORT}"
    )

    app.run(

        host="0.0.0.0",

        port=PORT,

        debug=False
    )