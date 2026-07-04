"""
Ethio Empire Bot
-----------------
Features:
1. Tutorial course sales — user pays, owner approves, bot sends private channel link
2. 🎵 Music search — user types artist/song name, bot shows list, user picks, bot sends audio

Owner commands:
  /setprice 500         - change the price
  /setpay <text>        - update Telebirr/CBE payment details
  /pending              - see who is waiting for approval
  /setlink <url>        - update the private channel invite link
"""

import json
import logging
import os
import asyncio

import yt_dlp
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ----------------------------------------------------------------------
# CONFIG — EDIT THESE LINES
# ----------------------------------------------------------------------

BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"   # from @BotFather
OWNER_ID  = 123456789                   # your numeric Telegram user ID

# ----------------------------------------------------------------------
# DEFAULT DATA
# ----------------------------------------------------------------------

DATA_FILE    = "data.json"
MUSIC_FOLDER = "downloads"
os.makedirs(MUSIC_FOLDER, exist_ok=True)

DEFAULT_DATA = {
    "price": 500,
    "currency": "ETB",
    "channel_link": "https://t.me/+wPe77gv04BIzZjQ0",
    "payment_instructions": (
        "Send the payment to:\n"
        "Telebirr: 09XXXXXXXX\n"
        "CBE Account: 1000XXXXXXXX\n"
        "Account Name: Ethio Empire\n\n"
        "After paying, send a screenshot of the receipt here."
    ),
    "pending": {},
    "approved": [],
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# In-memory search results per user: {user_id: [video_info, ...]}
user_search_cache = {}

# ----------------------------------------------------------------------
# DATABASE HELPERS
# ----------------------------------------------------------------------

def load_data() -> dict:
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return dict(DEFAULT_DATA)
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ----------------------------------------------------------------------
# YOUTUBE SEARCH HELPER
# ----------------------------------------------------------------------

def search_youtube(query: str, max_results: int = 8) -> list:
    """Search YouTube and return list of {title, url, duration, channel}."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "default_search": f"ytsearch{max_results}",
        "skip_download": True,
    }
    results = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=False)
        if "entries" in info:
            for entry in info["entries"]:
                if entry:
                    duration = entry.get("duration", 0)
                    mins = int(duration // 60) if duration else 0
                    secs = int(duration % 60) if duration else 0
                    results.append({
                        "title":    entry.get("title", "Unknown"),
                        "url":      f"https://www.youtube.com/watch?v={entry.get('id','')}",
                        "id":       entry.get("id", ""),
                        "duration": f"{mins}:{secs:02d}" if duration else "?:??",
                        "channel":  entry.get("channel") or entry.get("uploader", ""),
                    })
    return results

def download_audio(video_url: str, output_path: str) -> str:
    """Download audio from YouTube video. Returns the file path."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "outtmpl": output_path + ".%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    return output_path + ".mp3"

# ----------------------------------------------------------------------
# USER HANDLERS
# ----------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id

    if user_id in data["approved"]:
        await update.message.reply_text(
            f"✅ *Welcome back!*\n\nYou already have access.\n\n"
            f"🔗 {data['channel_link']}\n\n"
            f"🎵 *Music Search:* Just type any artist or song name and I'll find it for you!",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Buy Course Access", callback_data="show_payment")],
        [InlineKeyboardButton("🎵 Search Music (Free)", callback_data="music_help")],
    ])
    await update.message.reply_text(
        f"🎬 *Welcome to Ethio Empire!*\n\n"
        f"Get full access to *all* tutorial videos, PDFs, and tests.\n\n"
        f"💰 Price: *{data['price']} {data['currency']}*\n\n"
        f"🎵 *FREE:* Type any artist or song name to search and download music!\n\n"
        f"Example: just type *Leul Sisay* or *Teddy Afro*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )

async def music_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🎵 *Music Search — FREE!*\n\n"
        "Just type the name of any artist or song directly in the chat.\n\n"
        "*Examples:*\n"
        "• Leul Sisay\n"
        "• Teddy Afro\n"
        "• Zeritu Kebede\n"
        "• Yegna\n\n"
        "I will show you a list of songs to choose from! 🎶",
        parse_mode=ParseMode.MARKDOWN,
    )

async def show_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = load_data()
    await query.message.reply_text(
        f"💰 *Price: {data['price']} {data['currency']}*\n\n"
        f"{data['payment_instructions']}\n\n"
        f"📸 Once paid, send your receipt screenshot here.",
        parse_mode=ParseMode.MARKDOWN,
    )

# ----------------------------------------------------------------------
# 🎵 MUSIC SEARCH & DOWNLOAD
# ----------------------------------------------------------------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Any text message is treated as a music search query."""
    query = update.message.text.strip()
    user_id = update.effective_user.id

    if not query:
        return

    searching_msg = await update.message.reply_text(
        f"🔍 Searching for *{query}*...",
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, search_youtube, query)

        if not results:
            await searching_msg.edit_text("❌ No results found. Try a different search.")
            return

        # Cache results for this user
        user_search_cache[user_id] = results

        # Build inline keyboard — one button per result
        buttons = []
        for i, r in enumerate(results):
            label = f"• {r['duration']} • {r['title'][:45]}"
            buttons.append([InlineKeyboardButton(label, callback_data=f"play_{i}")])

        buttons.append([InlineKeyboardButton("+ More tracks", callback_data=f"more_{query}")])

        keyboard = InlineKeyboardMarkup(buttons)
        await searching_msg.edit_text(
            f"🎵 Results for *{query}*:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error("Search error: %s", e)
        await searching_msg.edit_text(
            "⚠️ Search failed. Please try again in a moment."
        )

async def play_song(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User taps a song from the list — download and send as audio."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    idx = int(query.data.split("_", 1)[1])
    results = user_search_cache.get(user_id, [])

    if not results or idx >= len(results):
        await query.message.reply_text("❌ Session expired. Please search again.")
        return

    song = results[idx]
    loading_msg = await query.message.reply_text(
        f"⬇️ Downloading *{song['title']}*...\nThis may take a few seconds ⏳",
        parse_mode=ParseMode.MARKDOWN,
    )

    output_path = os.path.join(MUSIC_FOLDER, f"{user_id}_{idx}")

    try:
        loop = asyncio.get_event_loop()
        audio_file = await loop.run_in_executor(
            None, download_audio, song["url"], output_path
        )

        await loading_msg.edit_text(f"📤 Sending *{song['title']}*...", parse_mode=ParseMode.MARKDOWN)

        with open(audio_file, "rb") as f:
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=f,
                title=song["title"],
                performer=song["channel"],
                caption=f"🎵 *{song['title']}*\n🎤 {song['channel']}\n\n_Ethio Empire Music Bot_",
                parse_mode=ParseMode.MARKDOWN,
            )

        await loading_msg.delete()

        # Clean up file
        if os.path.exists(audio_file):
            os.remove(audio_file)

    except Exception as e:
        logger.error("Download error: %s", e)
        await loading_msg.edit_text(
            "⚠️ Could not download this track. Please try another one."
        )
        if os.path.exists(output_path + ".mp3"):
            os.remove(output_path + ".mp3")

async def more_tracks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    search_query = query.data.split("_", 1)[1]
    await query.message.reply_text(
        f"🔍 Type *{search_query}* again to get a fresh set of results, "
        f"or try a more specific search like *{search_query} new song*.",
        parse_mode=ParseMode.MARKDOWN,
    )

# ----------------------------------------------------------------------
# PAYMENT PROOF
# ----------------------------------------------------------------------

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user = update.effective_user

    if user.id in data["approved"]:
        await update.message.reply_text(
            f"✅ You already have access!\n\n🔗 {data['channel_link']}"
        )
        return

    data["pending"][str(user.id)] = {
        "name": user.full_name,
        "username": user.username or "",
    }
    save_data(data)

    await update.message.reply_text(
        "✅ *Payment proof received!*\n\n"
        "Your screenshot has been sent for review.\n"
        "You will get the channel link automatically once approved. ⏳",
        parse_mode=ParseMode.MARKDOWN,
    )

    caption = (
        f"🧾 *New Payment Proof*\n"
        f"👤 Name: {user.full_name}\n"
        f"🔖 Username: @{user.username or 'none'}\n"
        f"🆔 User ID: {user.id}"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{user.id}"),
        ]
    ])
    photo_file_id = update.message.photo[-1].file_id
    await context.bot.send_photo(
        chat_id=OWNER_ID,
        photo=photo_file_id,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )

# ----------------------------------------------------------------------
# OWNER APPROVAL
# ----------------------------------------------------------------------

async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.from_user.id != OWNER_ID:
        await query.answer("Owner only.", show_alert=True)
        return

    parts = query.data.split("_", 1)
    action  = parts[0]
    user_id = int(parts[1])
    data    = load_data()

    if action == "approve":
        data["pending"].pop(str(user_id), None)
        if user_id not in data["approved"]:
            data["approved"].append(user_id)
        save_data(data)
        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n✅ APPROVED",
            parse_mode=ParseMode.MARKDOWN,
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"🎉 *Payment Approved! Welcome to Ethio Empire!*\n\n"
                f"🔗 {data['channel_link']}\n\n"
                f"_Keep this link private — it is only for you._\n\n"
                f"🎵 *Bonus:* Type any artist name to search and download music free!"
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    elif action == "reject":
        data["pending"].pop(str(user_id), None)
        save_data(data)
        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n❌ REJECTED",
            parse_mode=ParseMode.MARKDOWN,
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                "❌ *Payment could not be verified.*\n\n"
                "Please make sure the screenshot clearly shows:\n"
                "• The amount sent\n"
                "• The recipient account\n"
                "• The transaction confirmation\n\n"
                "Send a new screenshot or contact support."
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

# ----------------------------------------------------------------------
# OWNER COMMANDS
# ----------------------------------------------------------------------

def owner_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("This command is owner-only.")
            return
        return await func(update, context)
    return wrapper

@owner_only
async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /setprice 500")
        return
    try:
        price = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: /setprice 500")
        return
    data = load_data()
    data["price"] = price
    save_data(data)
    await update.message.reply_text(f"✅ Price updated to {price} {data['currency']}.")

@owner_only
async def setpay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.partition(" ")[2]
    if not text:
        await update.message.reply_text("Usage: /setpay <your payment details text>")
        return
    data = load_data()
    data["payment_instructions"] = text
    save_data(data)
    await update.message.reply_text("✅ Payment instructions updated.")

@owner_only
async def setlink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /setlink https://t.me/+xxxxxxx")
        return
    link = context.args[0]
    data = load_data()
    data["channel_link"] = link
    save_data(data)
    await update.message.reply_text(f"✅ Channel link updated to:\n{link}")

@owner_only
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if not data["pending"]:
        await update.message.reply_text("No pending payments right now.")
        return
    lines = [
        f"• {info['name']} (@{info['username'] or 'none'}) — ID: {uid}"
        for uid, info in data["pending"].items()
    ]
    await update.message.reply_text(
        "⏳ *Pending Payments:*\n" + "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
    )

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit("❌ Please set BOT_TOKEN at the top of bot.py first.")
    if OWNER_ID == 123456789:
        raise SystemExit("❌ Please set OWNER_ID at the top of bot.py to your Telegram user ID.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("setprice", setprice))
    app.add_handler(CommandHandler("setpay",   setpay))
    app.add_handler(CommandHandler("setlink",  setlink))
    app.add_handler(CommandHandler("pending",  pending_cmd))

    app.add_handler(CallbackQueryHandler(show_payment,      pattern="^show_payment$"))
    app.add_handler(CallbackQueryHandler(music_help,        pattern="^music_help$"))
    app.add_handler(CallbackQueryHandler(play_song,         pattern="^play_\\d+$"))
    app.add_handler(CallbackQueryHandler(more_tracks,       pattern="^more_"))
    app.add_handler(CallbackQueryHandler(approval_callback, pattern="^(approve|reject)_"))

    # Photo = payment proof
    app.add_handler(MessageHandler(filters.PHOTO, receive_proof))

    # Any text = music search
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Ethio Empire bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
