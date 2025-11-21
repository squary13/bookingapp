# telegram_bot.py
import os
import re
import logging
import urllib.parse
import requests
from typing import List

from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, WebAppInfo
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler, CallbackQueryHandler
)

# === CONFIG ===
API_URL = "https://booking-worker-py-be.squary50.workers.dev/api"  # PROD backend base
BOT_TOKEN = os.getenv("BOT_TOKEN", "7364112514:AAGi4LAVefHuljYgSIPbxvQK-Kvs_yvW4Tk")

CHOOSING_DATE, CHOOSING_TIME, ENTER_NAME, ENTER_PHONE = range(4)
DEFAULT_SLOTS: List[str] = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_slots_table(slots: List[str]) -> str:
    header = "🗓️ Доступные слоты:\n\n"
    rows = ""
    for i in range(0, len(slots), 3):
        row = " | ".join(f"{slot:^8}" for slot in slots[i:i + 3])
        rows += row + "\n"
    return header + "```\n" + rows + "```"


def is_valid_date(date_str: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str))


# === API HELPERS ===
def api_get(path: str, params: dict | None = None):
    url = f"{API_URL}{path}"
    print(f"GET → {url}")
    try:
        r = requests.get(url, params=params, timeout=10)
        print(f"Status: {r.status_code}, Body: {r.text}")
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"❌ API GET error: {e}")
        raise



def api_post(path: str, json: dict):
    url = f"{API_URL}{path}"
    r = requests.post(url, json=json, timeout=10)
    r.raise_for_status()
    return r


def api_delete(path: str):
    url = f"{API_URL}{path}"
    r = requests.delete(url, timeout=10)
    r.raise_for_status()
    return r


# === HANDLERS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    full_name = f"{first_name} {last_name}".strip()

    encoded_name = urllib.parse.quote(full_name)
    telegram_id = user.id
    web_app_url = f"https://booking-working-app-fe.pages.dev/?name={encoded_name}&user_id={telegram_id}"


    keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton("📲 Открыть мини-приложение", web_app=WebAppInfo(url=web_app_url))]],
        resize_keyboard=True
    )

    await update.message.reply_text(
        f"Добро пожаловать, {full_name}! Открой мини-приложение для записи:",
        reply_markup=keyboard
    )


async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "На какую дату хотите записаться? Введите в формате YYYY-MM-DD (например, 2025-11-20)"
    )
    return CHOOSING_DATE


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text.strip()
    if not is_valid_date(date):
        await update.message.reply_text("Дата в неверном формате. Попробуйте ещё раз: YYYY-MM-DD")
        return CHOOSING_DATE

    context.user_data["date"] = date

    try:
        r = api_get("/bookings/by-user/1000")
        all_slots = r.json()
        slots = [s["time"] for s in all_slots if s["date"] == date and str(s["user_id"]) == "6"]
    except Exception as e:
        logger.error(f"Ошибка при получении слотов: {e}")
        await update.message.reply_text("❌ Не удалось загрузить слоты. Попробуйте позже.")
        return ConversationHandler.END

    if not slots:
        await update.message.reply_text("⚠️ На выбранную дату нет свободных слотов.")
        return ConversationHandler.END

    await update.message.reply_text(format_slots_table(slots), parse_mode="Markdown")
    markup = ReplyKeyboardMarkup([[slot] for slot in slots], one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text("Выберите время:", reply_markup=markup)
    return CHOOSING_TIME



async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time = update.message.text.strip()
    if time not in DEFAULT_SLOTS:
        await update.message.reply_text("Такого слота нет. Выберите из списка.")
        return CHOOSING_TIME

    context.user_data["time"] = time
    await update.message.reply_text("Введите ваше имя:", reply_markup=ReplyKeyboardRemove())
    return ENTER_NAME


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Имя не может быть пустым. Введите ваше имя:")
        return ENTER_NAME

    context.user_data["name"] = name
    await update.message.reply_text("Введите ваш телефон (например, +37120000000):")
    return ENTER_PHONE


async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone:
        await update.message.reply_text("Телефон не может быть пустым. Введите ваш телефон:")
        return ENTER_PHONE

    context.user_data["phone"] = phone
    telegram_id = update.effective_user.id

    try:
        # Сначала ищем по telegram_id
        r = api_get("/users", params={"telegram_id": telegram_id})
        users = r.json()
        if isinstance(users, list) and users:
            user_id = users[0]["id"]
        else:
            # Если не найден — ищем по phone
            r = api_get("/users", params={"phone": phone})
            users = r.json()
            if isinstance(users, list) and users:
                user_id = users[0]["id"]
            else:
                # Если вообще не найден — создаём нового
                payload = {
                    "telegram_id": telegram_id,
                    "name": context.user_data["name"],
                    "phone": phone,
                    "role": "user"
                }
                r = api_post("/users", json=payload)
                user_id = r.json().get("id")
    except Exception as e:
        logger.error(f"Ошибка при получении/создании пользователя: {e}")
        await update.message.reply_text("Ошибка при регистрации. Попробуйте позже.")
        return ConversationHandler.END

    booking_payload = {
        "user_id": user_id,
        "date": context.user_data["date"],
        "time": context.user_data["time"]
    }

    try:
        r = requests.post(f"{API_URL}/bookings", json=booking_payload, timeout=10)
        if r.status_code == 201:
            await update.message.reply_text("✅ Вы успешно записаны!")
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Мои записи", callback_data="show_bookings")]
            ])
            await update.message.reply_text("Что дальше?", reply_markup=keyboard)
        else:
            err = r.json().get("error") if r.headers.get("content-type", "").startswith("application/json") else r.text
            await update.message.reply_text(f"Ошибка: {err or 'Не удалось создать запись'}")
    except Exception as e:
        logger.error(f"Ошибка при создании записи: {e}")
        await update.message.reply_text("Ошибка при бронировании. Попробуйте позже.")

    return ConversationHandler.END




async def send_bookings(chat_id: int, telegram_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = api_get(f"/bookings/by-user/{telegram_id}")
        bookings = r.json()
        if not isinstance(bookings, list) or not bookings:
            await context.bot.send_message(chat_id, "У вас нет записей.")
            return

        for b in bookings:
            text = f"📅 {b.get('date')} в {b.get('time')}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Удалить", callback_data=f"delete:{b.get('id')}")]
            ])
            await context.bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при получении записей: {e}")
        await context.bot.send_message(chat_id, "Ошибка при получении записей. Попробуйте позже.")


async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    chat_id = update.effective_chat.id
    await send_bookings(chat_id, telegram_id, context)


async def show_bookings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    telegram_id = query.from_user.id
    chat_id = query.message.chat_id
    await send_bookings(chat_id, telegram_id, context)


async def delete_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    booking_id = query.data.split(":")[1]

    try:
        r = api_delete(f"/bookings/{booking_id}")
        if r.status_code == 200:
            await query.edit_message_text("✅ Запись удалена.")
        else:
            await query.edit_message_text("❌ Ошибка при удалении.")
    except Exception as e:
        logger.error(f"Ошибка при удалении записи: {e}")
        await query.edit_message_text("❌ Ошибка при удалении.")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Запись отменена. Напишите /book, чтобы начать заново.")
    return ConversationHandler.END


def main():
    token = BOT_TOKEN  # используем напрямую
    logger.info("Бот запускается...")
    app = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("book", book)],
        states={
            CHOOSING_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_date)],
            CHOOSING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)],
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Основные команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mybookings", my_bookings))

    # Inline‑кнопки
    app.add_handler(CallbackQueryHandler(delete_booking, pattern=r"^delete:\d+$"))
    app.add_handler(CallbackQueryHandler(show_bookings_callback, pattern=r"^show_bookings$"))

    # Диалог бронирования
    app.add_handler(conv_handler)

    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()


