import os

# --- Required ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "7864255983:AAE5cU2QIPb9cD01KUlruK8awRkA_JB9BF8")

# Telegram user ID of the person who will moderate photos (get yours from @userinfobot)
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# --- Tunables ---
DB_PATH = os.getenv("DB_PATH", "dating.db")

MIN_AGE = 18                # hard floor, enforced at registration
FREE_DAILY_LIKES = 10       # likes per day before hitting the paid-tier wall
BIO_MAX_LEN = 300
NAME_MAX_LEN = 40
CITY_MAX_LEN = 60
