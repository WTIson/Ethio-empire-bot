"""
Ethio Empire Bot
-----------------
Flow:
1. User /start -> sees price and "I Want To Pay" button
2. User sees your Telebirr/CBE payment details
3. User sends payment screenshot
4. You (owner) get the screenshot with Approve/Reject buttons
5. You tap Approve -> bot automatically sends the private channel link to user
6. User joins your private channel and gets access to ALL videos/PDFs

Owner commands:
  /setprice 500         - change the price
  /setpay <text>        - update your Telebirr/CBE payment details
  /pending              - see who is waiting for approval
  /setlink <url>        - update the private channel invite link
"""

import json
import logging
import os

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
# CONFIG — EDIT THESE TWO LINES
# ----------------------------------------------------------------------

BOT_TOKEN = "7864255983:AAE5cU2QIPb9cD01KUlruK8awRkA_JB9BF8"   # from @BotFather
OWNER_ID  = 6974850092                   # your numeric Telegram user ID

# ----------------------------------------------------------------------
# DEFAULT DATA
# ----------------------------------------------------------------------

DATA_FILE = "data.json"

DEFAULT_DATA = {
    "price": 500,
    "currency": "ETB",
    "channel_link": "https://t.me/+wPe77gv04BIzZjQ0",   # your private channel
    "payment_instructions": (
        "Send the payment to:\n"
        "Telebirr: 09XXXXXXXX\n"
        "CBE Account: 1000XXXXXXXX\n"
        "Account Name: Ethio Empire\n\n"
        "After paying, send a screenshot of the receipt here."
    ),
    "pending": {},     # {user_id_str: {"name": ..., "username": ...}}
    "approved": [],    # list of approved user_id integers
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

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
# USER HANDLERS
# ----------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    user_id = update.effective_user.id

    if user_id in data["approved"]:
        await update.message.reply_text(
            f"✅ *Welcome back!*\n\nYou already have access.\n\n"
            f"🔗 Join your private channel here:\n{data['channel_link']}",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 I Want To Pay", callback_data="show_payment")]
    ])
    await update.message.reply_text(
        f"🎬 *Welcome to Ethio Empire!*\n\n"
        f"Get full access to *all* tutorial videos, PDFs, and tests.\n\n"
        f"💰 Price: *{data['price']} {data['currency']}*\n\n"
        f"Tap the button below to see payment details.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )

async def show_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = load_data()
    await query.message.reply_text(
        f"💰 *Price: {data['price']} {data['currency']}*\n\n"
        f"{data['payment_instructions']}\n\n"
        f"📸 Once paid, send your receipt screenshot here and we will verify it.",
        parse_mode=ParseMode.MARKDOWN,
    )

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User sends payment screenshot -> forward to owner with Approve/Reject."""
    data = load_data()
    user = update.effective_user

    if user.id in data["approved"]:
        await update.message.reply_text(
            f"✅ You already have access!\n\n🔗 {data['channel_link']}"
        )
        return

    # Save as pending
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

    # Forward to owner
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
    action = parts[0]
    user_id = int(parts[1])
    data = load_data()

    if action == "approve":
        data["pending"].pop(str(user_id), None)
        if user_id not in data["approved"]:
            data["approved"].append(user_id)
        save_data(data)

        await query.edit_message_caption(
            caption=(query.message.caption or "") + "\n\n✅ APPROVED",
            parse_mode=ParseMode.MARKDOWN,
        )
        # Send the private channel link to the user automatically
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"🎉 *Payment Approved! Welcome to Ethio Empire!*\n\n"
                f"Tap the link below to join your private channel.\n"
                f"You will find all tutorial videos, PDFs, and tests inside.\n\n"
                f"🔗 {data['channel_link']}\n\n"
                f"_Keep this link private — it is only for you._"
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

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("setprice", setprice))
    app.add_handler(CommandHandler("setpay",  setpay))
    app.add_handler(CommandHandler("setlink", setlink))
    app.add_handler(CommandHandler("pending", pending_cmd))

    app.add_handler(CallbackQueryHandler(show_payment,      pattern="^show_payment$"))
    app.add_handler(CallbackQueryHandler(approval_callback, pattern="^(approve|reject)_"))

    app.add_handler(MessageHandler(filters.PHOTO, receive_proof))

    logger.info("Ethio Empire bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
