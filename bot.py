"""
Ethio Empire Bot - Full Version
---------------------------------
Flow:
1. User /start -> sees subject menu (e.g. Math, Physics, etc.)
2. User picks a subject -> sees price + "I Want To Pay" button
3. User sends payment screenshot
4. Owner gets the screenshot with Approve/Reject buttons (showing which subject)
5. Owner taps Approve -> user gets access to that subject
6. User sees subject content menu: Video | PDF | Test
7. User picks content type -> bot sends the file

Owner commands:
  /addsubject Name Price        - add a new subject
  /setpay <text>                - update payment instructions
  /pending                      - list pending payments
  /listsubjects                 - list all subjects and their prices
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
# CONFIG - EDIT THESE
# ----------------------------------------------------------------------

BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"   # from @BotFather
OWNER_ID  = 123456789                   # your numeric Telegram user ID

DATA_FILE = "data.json"

# ----------------------------------------------------------------------
# DEFAULT DATA STRUCTURE
# ----------------------------------------------------------------------
# Files folder structure:
#   files/
#     Math/
#       video.mp4
#       notes.pdf
#       test.pdf
#     Physics/
#       video.mp4
#       notes.pdf
#       test.pdf
#   ... and so on for each subject

DEFAULT_DATA = {
    "payment_instructions": (
        "Send the payment to:\n"
        "Telebirr: 09XXXXXXXX\n"
        "CBE Account: 1000XXXXXXXX\n"
        "Account Name: Ethio Empire\n\n"
        "After paying, send a screenshot of the receipt here."
    ),
    "subjects": {
        "Math": {"price": 500, "currency": "ETB"},
        "Physics": {"price": 500, "currency": "ETB"},
        "Chemistry": {"price": 500, "currency": "ETB"},
        "Biology": {"price": 500, "currency": "ETB"},
    },
    "pending": {},    # {user_id: {"name":..., "username":..., "subject":...}}
    "approved": {},   # {user_id: ["Math", "Physics", ...]}
}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# JSON DATABASE
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
# HELPERS
# ----------------------------------------------------------------------

def subject_menu_keyboard(data: dict) -> InlineKeyboardMarkup:
    """Build the main subject selection keyboard."""
    buttons = []
    for subject in data["subjects"]:
        price = data["subjects"][subject]["price"]
        currency = data["subjects"][subject]["currency"]
        buttons.append([InlineKeyboardButton(
            f"📚 {subject} — {price} {currency}",
            callback_data=f"subject_{subject}"
        )])
    return InlineKeyboardMarkup(buttons)

def content_menu_keyboard(subject: str) -> InlineKeyboardMarkup:
    """Build the content type keyboard for a subject."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Tutorial Video", callback_data=f"content_video_{subject}")],
        [InlineKeyboardButton("📄 PDF Notes",      callback_data=f"content_pdf_{subject}")],
        [InlineKeyboardButton("📝 Test",           callback_data=f"content_test_{subject}")],
        [InlineKeyboardButton("🔙 Back to Subjects", callback_data="back_to_subjects")],
    ])

def get_file_path(subject: str, content_type: str) -> str:
    """Return expected file path for a subject's content."""
    ext_map = {"video": "mp4", "pdf": "pdf", "test": "pdf"}
    name_map = {"video": "video", "pdf": "notes", "test": "test"}
    return os.path.join("files", subject, f"{name_map[content_type]}.{ext_map[content_type]}")

# ----------------------------------------------------------------------
# USER HANDLERS
# ----------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    keyboard = subject_menu_keyboard(data)
    await update.message.reply_text(
        "🎓 *Welcome to Ethio Empire!*\n\n"
        "Choose a subject below to get started.\n"
        "Each subject includes: 🎬 Video + 📄 PDF + 📝 Test",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )

async def handle_subject_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User taps a subject -> show price and pay button."""
    query = update.callback_query
    await query.answer()
    subject = query.data.replace("subject_", "")
    data = load_data()
    user_id = str(query.from_user.id)

    if subject not in data["subjects"]:
        await query.message.reply_text("Subject not found.")
        return

    info = data["subjects"][subject]
    approved_subjects = data["approved"].get(user_id, [])

    if subject in approved_subjects:
        await query.message.reply_text(
            f"✅ You already have access to *{subject}*!\nChoose what to study:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=content_menu_keyboard(subject),
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 I Want To Pay", callback_data=f"pay_{subject}")],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_subjects")],
    ])
    await query.message.reply_text(
        f"📚 *{subject}*\n\n"
        f"Price: *{info['price']} {info['currency']}*\n\n"
        f"You will get access to:\n"
        f"🎬 Tutorial Video\n📄 PDF Notes\n📝 Test\n\n"
        f"Tap below to see payment details.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )

async def handle_pay_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show payment instructions when user taps I Want To Pay."""
    query = update.callback_query
    await query.answer()
    subject = query.data.replace("pay_", "")
    data = load_data()

    # Store selected subject in user context
    context.user_data["pending_subject"] = subject

    await query.message.reply_text(
        f"💰 *Payment for: {subject}*\n\n"
        f"{data['payment_instructions']}\n\n"
        f"📸 After paying, send your receipt screenshot here.",
        parse_mode=ParseMode.MARKDOWN,
    )

async def handle_back_to_subjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = load_data()
    await query.message.reply_text(
        "🎓 *Ethio Empire — Choose a Subject*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=subject_menu_keyboard(data),
    )

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User sends payment screenshot -> forward to owner."""
    data = load_data()
    user = update.effective_user
    user_id = str(user.id)

    subject = context.user_data.get("pending_subject")
    if not subject:
        await update.message.reply_text(
            "Please first choose a subject and tap 'I Want To Pay', then send your screenshot."
        )
        return

    # Save to pending
    data["pending"][user_id] = {
        "name": user.full_name,
        "username": user.username or "",
        "subject": subject,
    }
    save_data(data)

    await update.message.reply_text(
        f"✅ Got your payment proof for *{subject}*!\n"
        f"Please wait while the owner reviews it. You'll get access automatically once approved.",
        parse_mode=ParseMode.MARKDOWN,
    )

    # Forward to owner with approve/reject buttons
    price = data["subjects"].get(subject, {}).get("price", "?")
    currency = data["subjects"].get(subject, {}).get("currency", "ETB")
    caption = (
        f"🧾 *New Payment Proof*\n"
        f"Subject: {subject} ({price} {currency})\n"
        f"From: {user.full_name} (@{user.username or 'no_username'})\n"
        f"User ID: {user.id}"
    )
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user.id}_{subject}"),
        InlineKeyboardButton("❌ Reject",  callback_data=f"reject_{user.id}_{subject}"),
    ]])
    photo_file_id = update.message.photo[-1].file_id
    await context.bot.send_photo(
        chat_id=OWNER_ID,
        photo=photo_file_id,
        caption=caption,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard,
    )

async def handle_content_select(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User picks Video / PDF / Test from the content menu."""
    query = update.callback_query
    await query.answer()

    # callback_data format: content_video_Math / content_pdf_Physics / content_test_Biology
    parts = query.data.split("_", 2)   # ["content", "video", "Math"]
    content_type = parts[1]
    subject = parts[2]

    data = load_data()
    user_id = str(query.from_user.id)
    approved_subjects = data["approved"].get(user_id, [])

    if subject not in approved_subjects:
        await query.message.reply_text(
            f"❌ You don't have access to *{subject}* yet. Please purchase it first.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    file_path = get_file_path(subject, content_type)
    if not os.path.exists(file_path):
        await query.message.reply_text(
            f"⚠️ The {content_type} for *{subject}* hasn't been uploaded yet. "
            f"Please contact the admin.",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    label_map = {"video": "🎬 Tutorial Video", "pdf": "📄 PDF Notes", "test": "📝 Test"}
    await query.message.reply_text(f"Sending {label_map[content_type]} for *{subject}*...", parse_mode=ParseMode.MARKDOWN)

    with open(file_path, "rb") as f:
        if content_type == "video":
            await context.bot.send_video(
                chat_id=query.from_user.id,
                video=f,
                caption=f"🎬 {subject} — Tutorial Video\nEthio Empire",
                supports_streaming=True,
            )
        else:
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=f,
                caption=f"{'📄' if content_type == 'pdf' else '📝'} {subject} — {'Notes' if content_type == 'pdf' else 'Test'}\nEthio Empire",
            )

# ----------------------------------------------------------------------
# OWNER APPROVAL HANDLER
# ----------------------------------------------------------------------

async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.from_user.id != OWNER_ID:
        await query.answer("Owner only.", show_alert=True)
        return

    # callback_data: approve_12345_Math or reject_12345_Math
    parts = query.data.split("_", 2)
    action = parts[0]
    user_id_int = int(parts[1])
    user_id_str = parts[1]
    subject = parts[2]

    data = load_data()

    if action == "approve":
        data["pending"].pop(user_id_str, None)
        if user_id_str not in data["approved"]:
            data["approved"][user_id_str] = []
        if subject not in data["approved"][user_id_str]:
            data["approved"][user_id_str].append(subject)
        save_data(data)

        await query.edit_message_caption(
            caption=(query.message.caption or "") + f"\n\n✅ APPROVED — {subject}"
        )
        await context.bot.send_message(
            chat_id=user_id_int,
            text=f"🎉 *Payment approved!*\nYou now have full access to *{subject}*.\nChoose what to study:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=content_menu_keyboard(subject),
        )

    elif action == "reject":
        data["pending"].pop(user_id_str, None)
        save_data(data)
        await query.edit_message_caption(
            caption=(query.message.caption or "") + f"\n\n❌ REJECTED — {subject}"
        )
        await context.bot.send_message(
            chat_id=user_id_int,
            text=f"❌ Your payment for *{subject}* could not be verified.\n"
                 f"Please contact support or try again with a clearer screenshot.",
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
async def addsubject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /addsubject Math 500"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addsubject SubjectName Price\nExample: /addsubject English 400")
        return
    name = context.args[0]
    try:
        price = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Price must be a number. Example: /addsubject English 400")
        return
    data = load_data()
    data["subjects"][name] = {"price": price, "currency": "ETB"}
    save_data(data)
    os.makedirs(os.path.join("files", name), exist_ok=True)
    await update.message.reply_text(
        f"✅ Subject *{name}* added at {price} ETB.\n"
        f"Now upload:\n"
        f"• files/{name}/video.mp4\n"
        f"• files/{name}/notes.pdf\n"
        f"• files/{name}/test.pdf\n"
        f"to your GitHub repo.",
        parse_mode=ParseMode.MARKDOWN,
    )

@owner_only
async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Usage: /setprice Math 600"""
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setprice SubjectName NewPrice\nExample: /setprice Math 600")
        return
    name = context.args[0]
    try:
        price = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Price must be a number.")
        return
    data = load_data()
    if name not in data["subjects"]:
        await update.message.reply_text(f"Subject '{name}' not found. Use /listsubjects to see all.")
        return
    data["subjects"][name]["price"] = price
    save_data(data)
    await update.message.reply_text(f"✅ Price for *{name}* updated to {price} ETB.", parse_mode=ParseMode.MARKDOWN)

@owner_only
async def setpay(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.partition(" ")[2]
    if not text:
        await update.message.reply_text("Usage: /setpay <your payment details>")
        return
    data = load_data()
    data["payment_instructions"] = text
    save_data(data)
    await update.message.reply_text("✅ Payment instructions updated.")

@owner_only
async def listsubjects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if not data["subjects"]:
        await update.message.reply_text("No subjects yet. Use /addsubject to add one.")
        return
    lines = [f"• {name}: {info['price']} {info['currency']}" for name, info in data["subjects"].items()]
    await update.message.reply_text("📚 *Current Subjects:*\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

@owner_only
async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data()
    if not data["pending"]:
        await update.message.reply_text("No pending payments.")
        return
    lines = [
        f"• {info['name']} (@{info['username']}) — {info['subject']}"
        for uid, info in data["pending"].items()
    ]
    await update.message.reply_text("⏳ *Pending Payments:*\n" + "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------

def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit("Set BOT_TOKEN at the top of bot.py first.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",        start))
    app.add_handler(CommandHandler("addsubject",   addsubject))
    app.add_handler(CommandHandler("setprice",     setprice))
    app.add_handler(CommandHandler("setpay",       setpay))
    app.add_handler(CommandHandler("listsubjects", listsubjects))
    app.add_handler(CommandHandler("pending",      pending_cmd))

    app.add_handler(CallbackQueryHandler(handle_subject_select,  pattern="^subject_"))
    app.add_handler(CallbackQueryHandler(handle_pay_button,      pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(handle_back_to_subjects,pattern="^back_to_subjects$"))
    app.add_handler(CallbackQueryHandler(handle_content_select,  pattern="^content_"))
    app.add_handler(CallbackQueryHandler(approval_callback,      pattern="^(approve|reject)_"))

    app.add_handler(MessageHandler(filters.PHOTO, receive_proof))

    logger.info("Ethio Empire bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
