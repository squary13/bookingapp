import requests
import logging
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler, CallbackQueryHandler
)

API_URL = "http://127.0.0.1:8787/api"
BOT_TOKEN = "7364112514:AAGi4LAVefHuljYgSIPbxvQK-Kvs_yvW4Tk"

CHOOSING_DATE, CHOOSING_TIME, ENTER_NAME, ENTER_PHONE = range(4)

logging.basicConfig(level=logging.INFO)

def format_slots_table(slots: list[str]) -> str:
    header = "🗓️ Доступные слоты:\n\n"
    rows = ""
    for i in range(0, len(slots), 3):
        row = " | ".join(f"{slot:^8}" for slot in slots[i:i+3])
        rows += row + "\n"
    return header + "```\n" + rows + "```"

# /start
from telegram import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup([
        [KeyboardButton("📲 Открыть мини-приложение", web_app=WebAppInfo(url="https://your-app-url.com"))]
    ], resize_keyboard=True)

    await update.message.reply_text(
        "Привет! Я бот для записи.\n\n"
        "📌 Доступные команды:\n"
        "/book — записаться\n"
        "/mybookings — посмотреть свои записи\n",
        reply_markup=keyboard
    )


# /book
async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("На какую дату хотите записаться? (в формате YYYY-MM-DD)")
    return CHOOSING_DATE

# Выбор даты
async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = update.message.text
    context.user_data["date"] = date
    try:
        r = requests.get(f"{API_URL}/slots", params={"date": date})
        r.raise_for_status()
        slots = r.json().get("available", [])
    except Exception as e:
        logging.error(f"Ошибка при получении слотов: {e}")
        await update.message.reply_text("Ошибка при получении слотов. Попробуйте позже.")
        return ConversationHandler.END

    if not slots:
        await update.message.reply_text("Нет свободных слотов на эту дату. Попробуйте другую.")
        return CHOOSING_DATE

    await update.message.reply_text(format_slots_table(slots), parse_mode="Markdown")
    markup = ReplyKeyboardMarkup([[slot] for slot in slots], one_time_keyboard=True)
    await update.message.reply_text("Выберите время:", reply_markup=markup)
    return CHOOSING_TIME

# Выбор времени
async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["time"] = update.message.text
    await update.message.reply_text("Введите ваше имя:", reply_markup=ReplyKeyboardRemove())
    return ENTER_NAME

# Ввод имени
async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text("Введите ваш телефон:")
    return ENTER_PHONE

# Ввод телефона и создание записи
async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    telegram_id = update.effective_user.id

    user_payload = {
        "telegram_id": telegram_id,
        "name": context.user_data["name"],
        "phone": context.user_data["phone"],
        "role": "user"
    }

    try:
        r = requests.get(f"{API_URL}/users/{telegram_id}")
        if r.status_code == 200:
            user_id = r.json()["id"]
        else:
            r = requests.post(f"{API_URL}/users", json=user_payload)
            r.raise_for_status()
            user_id = r.json()["id"]
    except Exception as e:
        logging.error(f"Ошибка при регистрации пользователя: {e}")
        await update.message.reply_text("Ошибка при регистрации. Попробуйте позже.")
        return ConversationHandler.END

    booking_payload = {
        "user_id": user_id,
        "date": context.user_data["date"],
        "time": context.user_data["time"]
    }

    try:
        r = requests.post(f"{API_URL}/bookings", json=booking_payload)
        if r.status_code == 201:
            await update.message.reply_text("✅ Вы успешно записаны!")
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Мои записи", callback_data="show_bookings")]
            ])
            await update.message.reply_text("Что дальше?", reply_markup=keyboard)
        else:
            await update.message.reply_text(f"Ошибка: {r.json().get('error')}")
    except Exception as e:
        logging.error(f"Ошибка при создании записи: {e}")
        await update.message.reply_text("Ошибка при бронировании. Попробуйте позже.")
    return ConversationHandler.END

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Запись отменена. Напишите /book, чтобы начать заново.")
    return ConversationHandler.END

# /mybookings и inline-кнопка
async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    try:
        r = requests.get(f"{API_URL}/users/{telegram_id}")
        if r.status_code != 200:
            await update.message.reply_text("Вы не зарегистрированы.")
            return

        user_id = r.json()["id"]
        r = requests.get(f"{API_URL}/bookings", params={"user_id": user_id})
        bookings = r.json()
        if not bookings:
            await update.message.reply_text("У вас нет записей.")
            return

        for booking in bookings:
            text = f"📅 {booking['date']} в {booking['time']}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Удалить", callback_data=f"delete:{booking['id']}")]
            ])
            await update.message.reply_text(text, reply_markup=keyboard)
    except Exception as e:
        logging.error(f"Ошибка при получении записей: {e}")
        await update.message.reply_text("Ошибка при получении записей. Попробуйте позже.")

# Обработчик inline-кнопки "Мои записи"
async def show_bookings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await my_bookings(update, context)

# Обработчик кнопки удаления
async def delete_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    booking_id = query.data.split(":")[1]

    try:
        r = requests.delete(f"{API_URL}/bookings/{booking_id}")
        if r.status_code == 200:
            await query.edit_message_text("✅ Запись удалена.")
        else:
            await query.edit_message_text("❌ Ошибка при удалении.")
    except Exception as e:
        logging.error(f"Ошибка при удалении записи: {e}")
        await query.edit_message_text("❌ Ошибка при удалении.")

# Запуск
def main():
    print("Бот запускается...")
    app = ApplicationBuilder().token("7364112514:AAGi4LAVefHuljYgSIPbxvQK-Kvs_yvW4Tk").build()

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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("mybookings", my_bookings))
    app.add_handler(CallbackQueryHandler(delete_booking, pattern=r"^delete:\d+$"))
    app.add_handler(CallbackQueryHandler(show_bookings_callback, pattern="^show_bookings$"))
    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()
