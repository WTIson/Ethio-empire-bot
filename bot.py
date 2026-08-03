import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

import config
import db

logging.basicConfig(level=logging.INFO)
router = Router()


# ---------------------------------------------------------------------------
# FSM states
# ---------------------------------------------------------------------------
class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    bio = State()
    photo = State()


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------
def gender_kb(prefix: str) -> ReplyKeyboardMarkup:
    labels = ["Male", "Female", "Other"] if prefix == "gender" else ["Male", "Female", "Any"]
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label)] for label in labels],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def swipe_kb(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👎 Pass", callback_data=f"swipe:pass:{target_id}"),
                InlineKeyboardButton(text="👍 Like", callback_data=f"swipe:like:{target_id}"),
            ],
            [InlineKeyboardButton(text="🚩 Report", callback_data=f"swipe:report:{target_id}")],
        ]
    )


def admin_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Approve", callback_data=f"mod:approve:{user_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"mod:reject:{user_id}"),
            ]
        ]
    )


# ---------------------------------------------------------------------------
# /start and registration flow
# ---------------------------------------------------------------------------
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if user and db.is_profile_complete(message.from_user.id):
        await message.answer(
            "Welcome back! Use /discover to see profiles, or /profile to review yours."
        )
        return

    await message.answer(
        "Welcome to Local Match 💜\n\n"
        "Let's set up your profile. This bot is for adults 18+ only.\n\n"
        "What's your name?"
    )
    await state.set_state(Registration.name)


@router.message(Registration.name)
async def reg_name(message: Message, state: FSMContext):
    name = message.text.strip()[: config.NAME_MAX_LEN]
    db.upsert_user_field(message.from_user.id, username=message.from_user.username, name=name)
    await message.answer("How old are you?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.age)


@router.message(Registration.age)
async def reg_age(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Please send your age as a number.")
        return
    age = int(message.text)
    if age < config.MIN_AGE:
        await message.answer(
            "Sorry, this bot is only available to users 18 and older. "
            "You can't register at this time."
        )
        await state.clear()
        return
    if age > 100:
        await message.answer("Please enter a realistic age.")
        return

    db.upsert_user_field(message.from_user.id, age=age)
    await message.answer("What's your gender?", reply_markup=gender_kb("gender"))
    await state.set_state(Registration.gender)


@router.message(Registration.gender, F.text.in_(["Male", "Female", "Other"]))
async def reg_gender(message: Message, state: FSMContext):
    db.upsert_user_field(message.from_user.id, gender=message.text.lower())
    await message.answer("Who are you interested in meeting?", reply_markup=gender_kb("pref"))
    await state.set_state(Registration.looking_for)


@router.message(Registration.gender)
async def reg_gender_invalid(message: Message):
    await message.answer("Please tap one of the buttons: Male, Female, or Other.")


@router.message(Registration.looking_for, F.text.in_(["Male", "Female", "Any"]))
async def reg_looking_for(message: Message, state: FSMContext):
    db.upsert_user_field(message.from_user.id, looking_for=message.text.lower())
    await message.answer("Which city are you in?", reply_markup=ReplyKeyboardRemove())
    await state.set_state(Registration.city)


@router.message(Registration.looking_for)
async def reg_looking_for_invalid(message: Message):
    await message.answer("Please tap one of the buttons: Male, Female, or Any.")


@router.message(Registration.city)
async def reg_city(message: Message, state: FSMContext):
    city = message.text.strip()[: config.CITY_MAX_LEN]
    db.upsert_user_field(message.from_user.id, city=city)
    await message.answer("Write a short bio (a sentence or two about you).")
    await state.set_state(Registration.bio)


@router.message(Registration.bio)
async def reg_bio(message: Message, state: FSMContext):
    bio = message.text.strip()[: config.BIO_MAX_LEN]
    db.upsert_user_field(message.from_user.id, bio=bio)
    await message.answer("Last step — send one photo of yourself for your profile.")
    await state.set_state(Registration.photo)


@router.message(Registration.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext, bot: Bot):
    file_id = message.photo[-1].file_id
    db.upsert_user_field(
        message.from_user.id, photo_file_id=file_id, photo_status="pending"
    )
    await state.clear()
    await message.answer(
        "Thanks! Your photo is being reviewed before your profile goes live. "
        "We'll notify you once it's approved."
    )

    if config.ADMIN_ID:
        u = db.get_user(message.from_user.id)
        caption = (
            f"🆕 New profile pending review\n\n"
            f"Name: {u['name']}\nAge: {u['age']}\nGender: {u['gender']}\n"
            f"City: {u['city']}\nBio: {u['bio']}\n"
            f"Telegram: @{u['username'] or 'N/A'} (id {u['user_id']})"
        )
        await bot.send_photo(
            config.ADMIN_ID, file_id, caption=caption, reply_markup=admin_kb(u["user_id"])
        )


@router.message(Registration.photo)
async def reg_photo_invalid(message: Message):
    await message.answer("Please send a photo (as an image, not a file).")


# ---------------------------------------------------------------------------
# Admin moderation
# ---------------------------------------------------------------------------
@router.callback_query(F.data.startswith("mod:"))
async def admin_moderate(callback: CallbackQuery, bot: Bot):
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("Not authorized.", show_alert=True)
        return

    _, action, user_id_str = callback.data.split(":")
    user_id = int(user_id_str)

    if action == "approve":
        db.set_photo_status(user_id, "approved")
        await bot.send_message(
            user_id, "✅ Your profile photo was approved! You're live. Use /discover to start matching."
        )
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ APPROVED")
    else:
        db.set_photo_status(user_id, "rejected")
        await bot.send_message(
            user_id,
            "❌ Your photo was rejected (doesn't meet our guidelines). "
            "Please send a new, appropriate photo of yourself to continue.",
        )
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ REJECTED")

    await callback.answer()


# ---------------------------------------------------------------------------
# Discovery / swiping
# ---------------------------------------------------------------------------
@router.message(Command("discover"))
async def cmd_discover(message: Message):
    await show_next_candidate(message)


async def show_next_candidate(message: Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user or not db.is_profile_complete(user_id):
        await message.answer("Please finish registration first with /start.")
        return
    if user["photo_status"] != "approved":
        await message.answer("Your profile is still pending photo review. Hang tight!")
        return

    if not user["is_premium"] and db.likes_today(user_id) >= config.FREE_DAILY_LIKES:
        await message.answer(
            f"You've hit your {config.FREE_DAILY_LIKES} free likes for today. "
            "Come back tomorrow, or upgrade to premium for unlimited likes. (/premium)"
        )
        return

    candidate = db.next_candidate(user_id)
    if not candidate:
        await message.answer("No new profiles right now — check back later!")
        return

    caption = (
        f"{candidate['name']}, {candidate['age']}\n"
        f"📍 {candidate['city']}\n\n"
        f"{candidate['bio']}"
    )
    await message.answer_photo(
        candidate["photo_file_id"], caption=caption, reply_markup=swipe_kb(candidate["user_id"])
    )


@router.callback_query(F.data.startswith("swipe:"))
async def handle_swipe(callback: CallbackQuery, bot: Bot):
    _, action, target_id_str = callback.data.split(":")
    target_id = int(target_id_str)
    from_id = callback.from_user.id

    if db.has_swiped(from_id, target_id):
        await callback.answer("Already handled this profile.")
        return

    if action == "report":
        db.add_report(from_id, target_id)
        db.record_swipe(from_id, target_id, "pass")
        await callback.answer("Report submitted. This profile will be reviewed.", show_alert=True)
        await callback.message.delete()
        return

    db.record_swipe(from_id, target_id, action)

    if action == "like":
        if db.mutual_like_exists(from_id, target_id):
            db.create_match(from_id, target_id)
            me = db.get_user(from_id)
            them = db.get_user(target_id)
            await bot.send_message(
                from_id,
                f"🎉 It's a match with {them['name']}! "
                f"Say hi: tg://user?id={them['user_id']}"
                + (f" (@{them['username']})" if them["username"] else ""),
            )
            await bot.send_message(
                target_id,
                f"🎉 It's a match with {me['name']}! "
                f"Say hi: tg://user?id={me['user_id']}"
                + (f" (@{me['username']})" if me["username"] else ""),
            )

    await callback.answer()
    await callback.message.delete()
    await show_next_candidate(callback.message)


# ---------------------------------------------------------------------------
# Misc commands
# ---------------------------------------------------------------------------
@router.message(Command("profile"))
async def cmd_profile(message: Message):
    u = db.get_user(message.from_user.id)
    if not u or not db.is_profile_complete(message.from_user.id):
        await message.answer("You haven't finished registration yet. Use /start.")
        return
    status = {"approved": "✅ live", "pending": "⏳ pending review", "rejected": "❌ rejected"}
    caption = (
        f"{u['name']}, {u['age']}\n📍 {u['city']}\n\n{u['bio']}\n\n"
        f"Status: {status.get(u['photo_status'], u['photo_status'])}"
    )
    await message.answer_photo(u["photo_file_id"], caption=caption)


@router.message(Command("premium"))
async def cmd_premium(message: Message):
    await message.answer(
        "Premium removes your daily like limit and lets you see who liked you first.\n\n"
        "Payments aren't wired up in this prototype yet — plug in Telegram's native "
        "Payments API (bot.send_invoice) here."
    )


async def main():
    db.init_db()
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
