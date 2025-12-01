import asyncio
import re
import time
from flask import Flask, request, jsonify
from pyrogram import Client
from pyrogram.errors import FloodWait
import threading

# === Configuration ===
API_ID = 21313094
API_HASH = "80444108dac58a5d7d49292a7fbc5fbc"
SESSION_STRING = "BQFFNkYARW6FM22In8ztV6bnARvhJvNvvGEzEPdx9p0nx5YTW-QhiY2T-d5K08TEzRbrD4fzlPN_50kz8fMeHKXE_NK6OF3OwxjH0U1PjxpfZZdTWVKQBu3PNEMdDX9EBqOb6K5GCaOUTyBSX7JxjDDz2CcgmXycmqPMJ9oyRoNNmBnXRx4tPbnZPWDyiOBY5-kHPSuVxKHfPJTYeNRo3Seb7SR74ssfG0ZAyF1UqR5Q8B1kQwb9Hcp4P4Zz8UR1_Iv1O8SdOrZVmoQbggzQ7GTwqDiWSjxG7_yboboUaHeuU0-SmFKTIudPsKXOE46TIkGB7cWNJJ7wyXlwquT6gjRiVREL-wAAAAHF5oI3AA"

TARGET_BOT = "@telebrecheddb_bot"

app = Flask(__name__)

tg_client = Client(
    "session",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    no_updates=True
)

tg_loop = asyncio.new_event_loop()
tg_ready = False


def parse_bot_response(text: str) -> dict:
    text = text.replace("Телефон", "Phone") \
               .replace("История изменения имени", "Name change history") \
               .replace("Интересовались этим", "Viewed by")

    data = {
        "success": True,
        "username": None,
        "id": None,
        "phone": None,
        "viewed_by": None,
        "name_history": []
    }

    u = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
    if u: data["username"] = u.group(1)

    i = re.search(r"ID[:： ]+(\d+)", text)
    if i: data["id"] = i.group(1)

    p = re.search(r"Phone[:： ]+(\d+)", text)
    if p: data["phone"] = p.group(1)

    v = re.search(r"Viewed by[:： ]*(\d+)", text)
    if v: data["viewed_by"] = int(v.group(1))

    hist = re.findall(r"(\d{2}\.\d{2}\.\d{4}) → @([\w\d_]+),\s*([\w\d, ]+)", text)
    for d, u, ids in hist:
        found_ids = re.findall(r"\d+", ids)
        data["name_history"].append({
            "date": d,
            "username": u,
            "id": found_ids[0] if found_ids else None
        })

    return data


async def send_and_wait(username: str) -> dict:
    username = username.strip().lstrip("@")
    message_to_send = f"t.me/{username}"

    try:
        sent = await tg_client.send_message(TARGET_BOT, message_to_send)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        sent = await tg_client.send_message(TARGET_BOT, message_to_send)
    except Exception as e:
        return {"success": False, "error": f"Error contacting bot: {e}"}

    reply = None
    start = time.time()

    while time.time() - start < 60:
        async for msg in tg_client.get_chat_history(TARGET_BOT, limit=10):
            if msg.id > sent.id and not msg.outgoing and msg.text:
                reply = msg.text
                break
        if reply:
            break
        await asyncio.sleep(2)

    if not reply:
        return {"success": False, "error": "Bot did not reply within 60 seconds."}

    return parse_bot_response(reply)


@app.route("/check")
def check():
    global tg_ready
    if not tg_ready:
        return jsonify({"success": False, "error": "Telegram client not ready yet."})

    username = request.args.get("username")
    if not username:
        return jsonify({"success": False, "error": "Missing 'username' parameter"}), 400

    try:
        future = asyncio.run_coroutine_threadsafe(send_and_wait(username), tg_loop)
        result = future.result(timeout=70)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/")
def home():
    return jsonify({"status": "running", "telegram_ready": tg_ready})


async def start_tg():
    global tg_ready
    await tg_client.start()
    tg_ready = True


def loop_thread():
    tg_loop.create_task(start_tg())
    tg_loop.run_forever()


if __name__ == "__main__":
    threading.Thread(target=loop_thread, daemon=True).start()
    from keep_alive import keep_alive
    keep_alive()