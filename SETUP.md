# Ethio Empire Bot — Full Setup Guide

## Folder structure needed on GitHub
```
ethio-empire-bot/
├── bot.py
├── requirements.txt
├── files/
│   ├── Math/
│   │   ├── video.mp4
│   │   ├── notes.pdf
│   │   └── test.pdf
│   ├── Physics/
│   │   ├── video.mp4
│   │   ├── notes.pdf
│   │   └── test.pdf
│   ├── Chemistry/
│   │   ├── video.mp4
│   │   ├── notes.pdf
│   │   └── test.pdf
│   └── Biology/
│       ├── video.mp4
│       ├── notes.pdf
│       └── test.pdf
```

## Step 1 — Edit bot.py
Open bot.py in GitHub, tap the pencil icon and change:
```python
BOT_TOKEN = "your token from @BotFather"
OWNER_ID  = your numeric ID from @userinfobot
```

## Step 2 — Upload your files
In GitHub, create the folders above and upload each subject's:
- video.mp4 (tutorial video)
- notes.pdf (PDF notes)
- test.pdf  (test/exam file)

## Step 3 — Deploy on Railway
1. Go to railway.app
2. New Project → Deploy from GitHub repo
3. Pick your repo
4. Set Start Command: python bot.py
5. Done — Railway runs it 24/7

## Owner Commands (send these to your bot in Telegram)
| Command | What it does |
|---|---|
| /addsubject English 400 | Add a new subject at 400 ETB |
| /setprice Math 600 | Change Math price to 600 ETB |
| /setpay <text> | Update payment instructions |
| /listsubjects | See all subjects and prices |
| /pending | See who's waiting for approval |

## How the user flow works
1. User sends /start → sees subject menu with prices
2. Taps a subject → sees price + "I Want To Pay" button
3. Taps pay → sees your Telebirr/CBE details
4. Pays and sends screenshot
5. YOU get the screenshot with ✅ Approve / ❌ Reject buttons
6. Tap Approve → user instantly gets content menu for that subject
7. User picks 🎬 Video / 📄 PDF / 📝 Test → file is sent automatically

## Changing subjects later
- Add new subject: /addsubject SubjectName Price (then upload files to GitHub)
- Change price: /setprice SubjectName NewPrice
- Change payment info: /setpay your new details here
