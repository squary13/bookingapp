import os, re, logging, urllib.parse, requests
from typing import List
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, WebAppInfo
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler
)
from telegram.ext import MessageHandler, filters


API_URL = "https://booking-worker-py-be.squary50.workers.dev/api"
BOT_TOKEN = os.getenv("BOT_TOKEN", "7364112514:AAGi4LAVefHuljYgSIPbxvQK-Kvs_yvW4Tk")
CHOOSING_DATE, CHOOSING_TIME, ENTER_NAME, ENTER_PHONE = range(4)
DEFAULT_SLOTS: List[str] = ["10:00", "11:00", "12:00", "14:00", "15:00", "16:00"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def api_get(path: str, params: dict | None = None):
    url = f"{API_URL}{path}"
    return requests.get(url, params=params, timeout=10)


def api_post(path: str, json: dict):
    url = f"{API_URL}{path}"
    return requests.post(url, json=json, timeout=10)


def api_delete(path: str):
    url = f"{API_URL}{path}"
    return requests.delete(url, timeout=10)


def is_valid_date(date_str: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    encoded_name = urllib.parse.quote(full_name)
    telegram_id = user.id
    web_app_url = f"https://booking-working-app-fe.pages.dev/?name={encoded_name}&user_id={telegram_id}"

    keyboard = [[KeyboardButton("📲 Открыть мини-приложение", web_app=WebAppInfo(url=web_app_url))]]
    await update.message.reply_text(
        f"Добро пожаловать, {full_name}! Открой мини-приложение для записи:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите дату в формате YYYY-MM-DD:")
    return CHOOSING_DATE


async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text.strip()
    if not is_valid_date(date):
        await update.message.reply_text("Неверный формат. Пример: 2025-12-01")
        return CHOOSING_DATE

    context.user_data["date"] = date
    try:
        r = api_get("/bookings/by-user/999998")
        slots = [s["time"] for s in r.json() if s.get("date") == date]
        context.user_data["available_slots"] = slots
    except:
        await update.message.reply_text("❌ Ошибка загрузки слотов.")
        return ConversationHandler.END

    if not slots:
        await update.message.reply_text("⚠️ Нет доступных слотов.")
        return ConversationHandler.END

    buttons = [[InlineKeyboardButton(slot, callback_data=f"time:{slot}")] for slot in slots]
    await update.message.reply_text("Выберите время:", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSING_TIME


async def choose_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time = update.callback_query.data.split(":")[1]
    await update.callback_query.answer()
    context.user_data["time"] = time
    await update.callback_query.message.reply_text("Введите ваше имя:")
    return ENTER_NAME


async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["name"] = name
    await update.message.reply_text("Введите ваш телефон:")
    return ENTER_PHONE


async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data["phone"] = phone
    telegram_id = update.effective_user.id

    try:
        r = api_get("/users", {"telegram_id": telegram_id})
        users = r.json()
        if users:
            user_id = users[0]["id"]
        else:
            r = api_post("/users", {
                "telegram_id": telegram_id,
                "name": context.user_data["name"],
                "phone": phone,
                "role": "user"
            })
            user_id = r.json().get("id")
    except:
        await update.message.reply_text("❌ Ошибка регистрации.")
        return ConversationHandler.END

    booking = {
        "user_id": user_id,
        "date": context.user_data["date"],
        "time": context.user_data["time"]
    }

    try:
        r = api_post("/bookings", booking)
        if r.status_code == 201:
            await update.message.reply_text("✅ Запись создана!")
            buttons = [
                [InlineKeyboardButton("📋 Мои записи", callback_data="show_bookings")],
                [InlineKeyboardButton("🔁 Записаться снова", callback_data="book_again")]
            ]
            await update.message.reply_text("Что дальше?", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text("❌ Ошибка записи.")
    except:
        await update.message.reply_text("❌ Ошибка соединения.")
    return ConversationHandler.END


async def send_bookings(chat_id: int, telegram_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        r = api_get(f"/bookings/by-user/{telegram_id}")
        bookings = r.json()
        if not bookings:
            await context.bot.send_message(chat_id, "У вас нет записей.")
            return

        for b in bookings:
            text = f"📅 {b['date']} в {b['time']}"
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Удалить", callback_data=f"delete:{b['id']}")]])
            await context.bot.send_message(chat_id, text, reply_markup=btn)
    except:
        await context.bot.send_message(chat_id, "❌ Ошибка загрузки записей.")


async def show_bookings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await send_bookings(update.effective_chat.id, update.effective_user.id, context)


async def delete_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    booking_id = update.callback_query.data.split(":")[1]
    try:
        r = api_delete(f"/bookings/{booking_id}")
        if r.status_code == 200:
            await update.callback_query.edit_message_text("✅ Запись удалена.")
        else:
            await update.callback_query.edit_message_text("❌ Ошибка удаления.")
    except:
        await update.callback_query.edit_message_text("❌ Ошибка удаления.")


async def book_again_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("Введите дату в формате YYYY-MM-DD:")
    return CHOOSING_DATE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Запись отменена. Напишите /book, чтобы начать заново.")
    return ConversationHandler.END


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("book", book)],
        states={
            CHOOSING_DATE: [CommandHandler("cancel", cancel), CallbackQueryHandler(choose_time_callback, pattern="^time:")],
            CHOOSING_TIME: [CallbackQueryHandler(choose_time_callback, pattern="^time:")],
            ENTER_NAME: [CommandHandler("cancel", cancel), CallbackQueryHandler(book_again_callback, pattern="^book_again$"), MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(show_bookings_callback, pattern="^show_bookings$"))
    app.add_handler(CallbackQueryHandler(delete_booking, pattern="^delete:"))
    app.add_handler(CallbackQueryHandler(book_again_callback, pattern="^book_again$"))

    app.run_polling()


if __name__ == "__main__":
    main()
