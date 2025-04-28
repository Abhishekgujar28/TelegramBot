import nest_asyncio
nest_asyncio.apply()

import asyncio
import datetime
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)

# CONFIG 

TOKEN = "7721908110:AAHGl5eFR7c9ulXY1W0g7tFTfQXyrYpiPvM"
CHANNEL_ID = -1002674312529  # Your channel
OWNER_IDS = [7560481124, 7386570615]  # owners
SUBSCRIBER_ID =  8002072016 # subscriber

SUBSCRIPTION_FILE = 'subscription.json'

current_invite_link = None
show_link_for_owners = False
last_shown_time = {}

#SUBSCRIPTION

def load_subscription():
    if os.path.exists(SUBSCRIPTION_FILE):
        with open(SUBSCRIPTION_FILE, 'r') as f:
            data = json.load(f)
            return datetime.datetime.fromisoformat(data['subscription_end'])
    else:
        start = datetime.datetime.now()
        end = start + datetime.timedelta(days=1)
        save_subscription(end)
        return end

def save_subscription(subscription_end):
    with open(SUBSCRIPTION_FILE, 'w') as f:
        json.dump({'subscription_end': subscription_end.isoformat()}, f)

subscription_end = load_subscription()


async def generate_invite_link(application):
    global current_invite_link

    while True:
        try:
            bot = application.bot
            if current_invite_link:
                try:
                    await bot.revoke_chat_invite_link(CHANNEL_ID, current_invite_link)
                    print(f"[+] Revoked old link: {current_invite_link}")
                except Exception as e:
                    print(f"[!] Failed to revoke old link: {e}")

            expire_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
            new_link = await bot.create_chat_invite_link(
                chat_id=CHANNEL_ID,
                expire_date=expire_time,
                creates_join_request=False
            )

            current_invite_link = new_link.invite_link
            print(f"[+] New invite link created: {current_invite_link}")

        except Exception as e:
            print(f"[ERROR] Couldn't create invite link: {e}")

        await asyncio.sleep(900)  # 15m

async def send_invite_link(update: Update, text: str = "Here is your link! Click below 👇"):
    if current_invite_link:
        button = InlineKeyboardButton("🔔 Request to Join", url=current_invite_link)
    else:
        button = InlineKeyboardButton("🔁 Link is loading... Try again later", callback_data="no_link")
    keyboard = InlineKeyboardMarkup([[button]])
    await update.message.reply_text(text, reply_markup=keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global show_link_for_owners

    user_id = update.effective_user.id
    now = datetime.datetime.now()

    days_left = (subscription_end - now).days

    if user_id == SUBSCRIBER_ID:
        if now > subscription_end + datetime.timedelta(days=10):
            await update.message.reply_text("❌ Subscription expired and bot deactivated.")
            return

        if now > subscription_end:
            await update.message.reply_text("⚠️ Your subscription expired. Please renew to reactivate.")
            await send_invite_link(update)
            return

        if now - last_shown_time.get(user_id, datetime.datetime(1970, 1, 1)) > datetime.timedelta(hours=1):
            await update.message.reply_text(f"⏳ You have {days_left} days left in your subscription.")
            last_shown_time[user_id] = now

        await send_invite_link(update)

    elif user_id in OWNER_IDS:
        if show_link_for_owners:
            await send_invite_link(update, text="👑 Owner Access: Invite link below 👇")
        else:
            await update.message.reply_text(f"👑 You have {days_left} days left in subscriber's subscription.")

    else:
        await send_invite_link(update)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in OWNER_IDS:
        await update.message.reply_text(
            "👑 Owner Commands:\n\n"
            "/adddays X ➔ Add X days to subscriber\n"
            "/removedays X ➔ Remove X days\n"
            "/show ➔ Show link for owners\n"
            "/hide ➔ Hide link for owners\n"
            "/status ➔ Check subscription status\n"
            "/help ➔ Show this message"
        )
    else:
        await update.message.reply_text(
            "ℹ️ This bot provides invite links. Just use /start!"
        )

async def show_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global show_link_for_owners
    user_id = update.effective_user.id
    if user_id in OWNER_IDS:
        show_link_for_owners = True
        await update.message.reply_text("✅ Owners will now see invite link at /start.")

async def hide_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global show_link_for_owners
    user_id = update.effective_user.id
    if user_id in OWNER_IDS:
        show_link_for_owners = False
        await update.message.reply_text("✅ Owners will not see invite link at /start.")

async def add_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global subscription_end
    user_id = update.effective_user.id
    if user_id in OWNER_IDS:
        try:
            days = int(context.args[0])
            subscription_end += datetime.timedelta(days=days)
            save_subscription(subscription_end)
            await update.message.reply_text(f"✅ Added {days} days to subscription.")
        except:
            await update.message.reply_text("❌ Usage: /adddays X")

async def remove_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global subscription_end
    user_id = update.effective_user.id
    if user_id in OWNER_IDS:
        try:
            days = int(context.args[0])
            subscription_end -= datetime.timedelta(days=days)
            save_subscription(subscription_end)
            await update.message.reply_text(f"✅ Removed {days} days from subscription.")
        except:
            await update.message.reply_text("❌ Usage: /removedays X")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.datetime.now()
    days_left = (subscription_end - now).days

    if user_id == SUBSCRIBER_ID or user_id in OWNER_IDS:
        status = "🟢 ACTIVE" if now < subscription_end else "🔴 EXPIRED"

        await update.message.reply_text(
            f"📅 Subscription End Date: {subscription_end.strftime('%Y-%m-%d')}\n"
            f"⏳ Days Left: {max(days_left, 0)}\n"
            f"⚡ Status: {status}"
        )
    else:
        await update.message.reply_text("❌ You are not authorized to view subscription status.")

async def notify_before_expiry(application):
    bot = application.bot
    while True:
        now = datetime.datetime.now()
        days_left = (subscription_end - now).days

        if days_left == 1:
            try:
                await bot.send_message(SUBSCRIBER_ID, "⚠️ Reminder: Your subscription will expire in 1 day!")
                for owner_id in OWNER_IDS:
                    await bot.send_message(owner_id, "⚠️ Subscriber's subscription will expire in 1 day.")
            except Exception as e:
                print(f"[Error sending expiry reminder]: {e}")

        await asyncio.sleep(86400)


async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("show", show_link))
    app.add_handler(CommandHandler("hide", hide_link))
    app.add_handler(CommandHandler("adddays", add_days))
    app.add_handler(CommandHandler("removedays", remove_days))
    app.add_handler(CommandHandler("status", status))

    asyncio.create_task(generate_invite_link(app))
    asyncio.create_task(notify_before_expiry(app))

    print("🤖 Bot is up and running!")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped manually.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        save_subscription(subscription_end)
