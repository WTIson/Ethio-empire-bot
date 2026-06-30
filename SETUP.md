# Ethio Empire Bot — Setup Guide

## 1. Create the bot on Telegram
1. Open Telegram, search for **@BotFather**.
2. Send `/newbot`, choose a name (e.g. "Ethio Empire") and a username ending in `bot`
   (e.g. `EthioEmpire_bot`).
3. BotFather gives you a **token** like `123456789:AAH...`. Copy it.

## 2. Get your own numeric Telegram user ID
1. In Telegram, search for **@userinfobot** and send it any message.
2. It replies with your numeric ID, e.g. `987654321`. This is your **OWNER_ID**.

## 3. Configure the bot
Open `bot.py` and edit these two lines near the top:

```python
BOT_TOKEN = "PUT_YOUR_BOT_TOKEN_HERE"   # paste the token from BotFather
OWNER_ID = 123456789                     # paste your numeric ID
```

Put your tutorial video file in the same folder and name it `tutorial_video.mp4`
(or change `VIDEO_PATH` in bot.py to match your filename).

## 4. Install and run
On your computer or server (needs Python 3.10+):

```bash
pip install -r requirements.txt
python bot.py
```

Leave it running (on a VPS, use something like `screen`, `tmux`, or a systemd
service so it stays online 24/7). Free options if you don't have a server yet:
Railway, Render, or PythonAnywhere all can keep a Python script running.

## 5. How it works day to day
- Anyone who messages your bot sees `/start`, the price, and a "I Want To Pay"
  button with your payment instructions.
- They send a screenshot of their payment as a photo in the chat.
- You (the owner) instantly get that screenshot forwarded to you with
  **Approve** / **Reject** buttons.
- Tap **Approve** → the bot automatically sends them the video.
- Tap **Reject** → they get a polite decline message.

## 6. Owner commands (only work for your OWNER_ID)
- `/setprice 500` — change the price shown to users (any number)
- `/setpay <text>` — change the payment instructions (your account numbers etc.)
- `/pending` — list everyone currently waiting for approval

## 7. Notes & ideas for later
- Right now "payment proof" is a manual photo your check yourself — this is
  the most reliable approach since Telegram Payments doesn't support
  Ethiopian banks/telebirr directly.
- If you later want **automatic** verification (no manual approval), you'd
  need to integrate a local payment gateway's API (e.g. Chapa, SantimPay)
  that can notify your bot when a payment succeeds — happy to help build
  that next if you're interested.
- All data (price, payment text, pending/approved users) is stored in
  `data.json` next to the script — back this file up.
