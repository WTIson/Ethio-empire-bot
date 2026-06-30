"""
Ethio Empire Bot
-----------------
A Telegram bot that sells access to a tutorial video.

Flow:
1. User runs /start -> sees price + "I Paid" button.
2. User sends payment proof (a photo of receipt/screenshot).
3. The proof is forwarded to the OWNER (you) with Approve/Reject buttons.
4. When you tap Approve, the bot automatically sends the tutorial video
   to that user. If you tap Reject, the user is notified.

You (the owner) control:
- The price (via /setprice command, or editing config.json)
- The video file (place it in the project folder and set VIDEO_PATH,
  or set VIDEO_FILE_ID after the bot has sent it once - see notes below)
- Payment instructions text (via /setpay command)

Run:
    pip install python-telegram-bot --upgrade
    python bot.py
"""

import json
import logging
import os

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------

BOT_TOKEN = "7864255983:AAE5cU2QIPb9cD01KUlruK8awRkA_JB9BF8"          # from @BotFather
OWNER_ID =   6974850092                          # your numeric Telegram user id (see notes.md)

DATA_FILE = "data.json"                         # stores price, payment info, approved users
VIDEO_PATH = "tutorial_video.mp4"                # put your video file here (same folder)

DEFAULT_DATA = {
    "price": 500,                  # ETB, change anytime with /setprice
    "currency": "ETB",
    "payment_instructions": (
        "Send the payment to:\n"
        "Telebirr: 0987015014\n"
        "CBE Account: 1000659611841\n"
        "Account Name: Ethio Empire\n\n"
        "After paying, send a screenshot of the receipt here."
    ),
    "pending": {},      # {user_id: {"name":..., "username":...}}
    "approved": [],     # list of user_ids who already received the video
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# SIMPLE JSON "DATABASE"
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
# USER-FACING HANDLERS
# ----------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id

    if user_id in data["approved"]:
        await update.message.reply_text(
            "Welcome back! You already have access. Use /getvideo to receive the video again."
        )
        return

    text = (
        f"🎬 *Welcome to Ethio Empire*\n\n"
        f"Get full access to the tutorial video for *{data['price']} {data['currency']}*.\n\n"
        f"Tap the button below to see payment details."
    )
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("💳 I Want To Pay", callback_data="show_payment")]]
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)


async def show_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = load_data()
    text = (
        f"💰 *Price:* {data['price']} {data['currency']}\n\n"
        f"{data['payment_instructions']}\n\n"
        f"📸 Once you've paid, just send the receipt screenshot in this chat."
    )
    await query.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User sends a photo (payment proof) -> forward to owner with approve/reject buttons."""
    data = load_data()
    user = update.effective_user

    if user.id in data["approved"]:
        await update.message.reply_text("You already have access. Use /getvideo.")
        return

    data["pending"][str(user.id)] = {
        "name": user.full_name,
        "username": user.username or "",
    }
    save_data(data)

    await update.message.reply_text(
        "✅ Thanks! Your payment proof was sent for review. "
        "You'll get the video automatically once approved."
    )

    caption = (
        f"🧾 New payment proof\n"
        f"From: {user.full_name} (@{user.username or 'no_username'})\n"
        f"User ID: {user.id}"
    )
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user.id}"),
            ]
        ]
    )

    # forward the actual photo to the owner
    photo_file_id = update.message.photo[-1].file_id
    await context.bot.send_photo(
        chat_id=OWNER_ID,
        photo=photo_file_id,
        caption=caption,
        reply_markup=keyboard,
    )


async def getvideo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id
    if user_id not in data["approved"]:
        await update.message.reply_text("You don't have access yet. Use /start to purchase.")
        return
    await send_video_to_user(context, user_id)


# ----------------------------------------------------------------------
# OWNER-ONLY HANDLERS
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
        new_price = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Please send a number, e.g. /setprice 500")
        return
    data = load_data()
    data["price"] = new_price
    save_data(data)
    await update.message.reply_text(f"✅ Price updated to {new_price} {data['currency']}.")


@owner_only
async def setpay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.partition(" ")[2]
    if not text:
        await update.message.reply_text("Usage: /setpay <payment instructions text>")
        return
    data = load_data()
    data["payment_instructions"] = text
    save_data(data)
    await update.message.reply_text("✅ Payment instructions updated.")


@owner_only
async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if not data["pending"]:
        await update.message.reply_text("No pending payments.")
        return
    lines = [f"{uid}: {info['name']} (@{info['username']})" for uid, info in data["pending"].items()]
    await update.message.reply_text("Pending:\n" + "\n".join(lines))


async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.from_user.id != OWNER_ID:
        await query.answer("Owner only.", show_alert=True)
        return

    action, user_id_str = query.data.split("_", 1)
    user_id = int(user_id_str)
    data = load_data()

    if action == "approve":
        data["pending"].pop(user_id_str, None)
        if user_id not in data["approved"]:
            data["approved"].append(user_id)
        save_data(data)

        await query.edit_message_caption(caption=query.message.caption + "\n\n✅ APPROVED")
        await send_video_to_user(context, user_id)
        await context.bot.send_message(
            chat_id=user_id, text="🎉 Payment approved! Here is your video."
        )

    elif action == "reject":
        data["pending"].pop(user_id_str, None)
        save_data(data)
        await query.edit_message_caption(caption=query.message.caption + "\n\n❌ REJECTED")
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ Your payment could not be verified. Please contact support or try again.",
        )


# ----------------------------------------------------------------------
# VIDEO DELIVERY
# ----------------------------------------------------------------------

async def send_video_to_user(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Sends the tutorial video. Uses local file the first few times;
    Telegram will cache it, and subsequent sends are instant."""
    if not os.path.exists(VIDEO_PATH):
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Video not configured yet. Please contact the admin.",
        )
        logger.warning("VIDEO_PATH file not found: %s", VIDEO_PATH)
        return

    with open(VIDEO_PATH, "rb") as video_file:
        await context.bot.send_video(
            chat_id=user_id,
            video=video_file,
            caption="🎬 Ethio Empire Tutorial — enjoy!",
            supports_streaming=True,
        )


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit(
            "Set BOT_TOKEN at the top of bot.py (get it from @BotFather in Telegram)."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("getvideo", getvideo))
    app.add_handler(CommandHandler("setprice", setprice))
    app.add_handler(CommandHandler("setpay", setpay))
    app.add_handler(CommandHandler("pending", pending))

    app.add_handler(CallbackQueryHandler(show_payment, pattern="^show_payment$"))
    app.add_handler(CallbackQueryHandler(approval_callback, pattern="^(approve|reject)_"))

    app.add_handler(MessageHandler(filters.PHOTO, receive_proof))

    logger.info("Ethio Empire bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
