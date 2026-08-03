# Local Match — Telegram Dating Bot (prototype)

A working prototype of a swipe-style dating bot: registration → admin photo
review → mutual-match swiping. Built with Python 3.11+, aiogram 3, and SQLite.

## Files

- `bot.py` — handlers: registration FSM, admin moderation, swipe/match loop
- `db.py` — SQLite schema + all queries (users, swipes, matches, reports)
- `config.py` — env vars and tunables (daily like limit, min age, etc.)
- `requirements.txt` — just `aiogram`

## 1. Get a bot token

1. Open Telegram, message **@BotFather**
2. `/newbot` → follow the prompts → copy the token it gives you

## 2. Get your own Telegram user ID (to be the moderator)

Message **@userinfobot** — it replies with your numeric ID.

## 3. Install & configure

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

export BOT_TOKEN="123456:ABC-your-token-here"
export ADMIN_ID="123456789"     # your Telegram user ID from step 2
```

(On Windows use `set BOT_TOKEN=...` instead of `export`.)

## 4. Run it

```bash
python3 bot.py
```

You should see aiogram start polling. Now open your bot in Telegram and hit
`/start`.

## 5. Try the full flow

1. Register with a test account: name → age (try under 18 to see the age
   gate) → gender → looking-for → city → bio → photo.
2. Your photo goes to **you** (the admin) as a pending-review card with
   Approve/Reject buttons — since in a real deployment ADMIN_ID is your
   account.
3. Approve it → the bot tells the user they're live.
4. Register a second test account (a friend, or Telegram's "add account")
   with a complementary gender/looking-for pairing, approve their photo too.
5. Run `/discover` on either account → swipe Like on the other → swipe Like
   back from the other account → both get a "It's a match!" message with a
   `tg://user?id=...` deep link to start chatting directly.
6. Try `/profile` to see your own status, and the 🚩 Report button to see
   how reports are logged (check the `reports` table in `dating.db`).

## What's stubbed vs. real

**Real and working:** registration validation (age gate, field limits),
photo moderation queue, swipe/pass/report logic, mutual-match detection,
daily like limit, SQLite persistence.

**Stubbed:** `/premium` — the paid tier is described but payment isn't
wired up. That's the first thing to extend (see below).

## What I'd extend first

1. **Payments** — replace the `/premium` stub with Telegram's native
   Payments API (`bot.send_invoice`, listen for `pre_checkout_query` and
   `successful_payment`). No manual screenshots needed; Telegram handles
   the transaction and you just flip `is_premium=1` in the `users` table
   on the `successful_payment` update. Also wire "unlimited likes" to check
   `is_premium` in `show_next_candidate` (already scaffolded).
2. **Photo moderation at scale** — right now every photo goes to one human
   admin. Add an auto-moderation pass first (an image-moderation API) to
   auto-reject obvious violations and only queue borderline cases for you.
3. **"See who liked you"** — a premium feature: query `swipes` for
   `to_id=me AND action='like' AND from_id NOT IN (my swipes)`.
4. **Distance-based matching** — currently matches are random within
   gender preference. Add lat/lon (via Telegram's native location share)
   and sort `next_candidate` by distance.
5. **Un-ban / appeal flow and admin commands** — `/ban <id>`, `/reports`
   list for the admin, since right now reports are logged but nothing acts
   on them automatically.
6. **Move off MemoryStorage** — FSM state is in-memory (`MemoryStorage`),
   so it resets on restart. Swap in `RedisStorage` for production so
   half-finished registrations survive a deploy.
7. **Photo count** — schema only stores one `photo_file_id`; extend to a
   `photos` table for multi-photo profiles (common expectation on any
   dating product).

## Safety notes already baked in

- Hard 18+ age gate at registration (rejects and clears state if under 18)
- No phone number collection, no forced photo-screenshot exchange
- Contact info (username/deep link) is only revealed after a **mutual**
  match — never before
- Report button on every profile shown during swiping
