import os
import sqlite3
import logging
import datetime

from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import pandas as pd

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Читаем токен из переменных среды
TOKEN = os.environ["BOT_TOKEN"]
# CHAT_ID = int(os.environ["CHAT_ID"])

# Подключаем SQLite
conn = sqlite3.connect("debts.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS debts (
        debtor TEXT,
        creditor TEXT,
        amount REAL
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS cards (
        username TEXT PRIMARY KEY,
        card_number TEXT
    )
""")
conn.commit()

# === Команды ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить расход", callback_data='add')],
        [InlineKeyboardButton("📊 Баланс братишек", callback_data='balance')],
        [InlineKeyboardButton("📊 Excel", callback_data='excel')],
        [InlineKeyboardButton("🔄 Обнулить все расчеты", callback_data='reset')],
        [InlineKeyboardButton("ℹ Помощь братишкам", callback_data='help')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Помни, бро! Кто платил, тот и вводит! 💸\nВыбери действие:",
        reply_markup=reply_markup
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        amount = float(args[0])

        mentions = [u.lstrip('@') for u in args if u.startswith('@')]
        description_words = [w for w in args[1:] if not w.startswith('@')]
        description = ' '.join(description_words)

        involved = list(set(mentions))
        payer = update.effective_user.username or update.effective_user.first_name
        if payer not in involved:
            involved.append(payer)

        if not involved:
            await update.message.reply_text("Укажи братишек после суммы и описания.")
            return

        split = round(amount / len(involved), 2)

        for user in involved:
            if user == payer:
                continue
            cursor.execute("INSERT INTO debts (debtor, creditor, amount) VALUES (?, ?, ?)",
                           (user, payer, split))
        conn.commit()

        await update.message.reply_text(
            f"{description}: {amount}₼ / {len(involved)} = {split}₼\n"
            f"{', '.join('@' + u for u in involved)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Показать баланс", callback_data='balance')]
            ])
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}\nФормат: /add 900 Ужин @user1 @user2")

# Команда для установки / обновления карты
async def set_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        card_number = context.args[0]
        username = update.effective_user.username
        if not username:
            await update.message.reply_text("У тебя нет username в Telegram, поэтому карту сохранить нельзя.")
            return

        if len(card_number) != 16 or not card_number.isdigit():
            await update.message.reply_text("Номер карты должен быть из 16 цифр.")
            return

        cursor.execute("REPLACE INTO cards (username, card_number) VALUES (?, ?)", (username, card_number))
        conn.commit()
        await update.message.reply_text("Карта успешно сохранена!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}\nИспользуй формат: /setcard 1234567812345678")

# Команда для просмотра карты другого пользователя
async def get_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Используй: /card @username")
        return

    username = context.args[0].lstrip('@')
    cursor.execute("SELECT card_number FROM cards WHERE username = ?", (username,))
    card = cursor.fetchone()

    if card:
        await update.message.reply_text(f"{card[0]}")
    else:
        await update.message.reply_text(f"У @{username} нет сохранённой карты.")

# === Обработчики кнопок ===

async def show_balance(message):
    cursor.execute("SELECT debtor, creditor, SUM(amount) FROM debts GROUP BY debtor, creditor")
    rows = cursor.fetchall()
    if not rows:
        await message.reply_text("Баланс пуст — братишки рассчитались 🙌")
        return

    lines = []
    for debtor, creditor, amount in rows:
        cursor.execute("SELECT card_number FROM cards WHERE username = ?", (creditor,))
        card = cursor.fetchone()
        card_info = card[0] if card else "Карта не указана"
        lines.append(f"@{debtor} должен @{creditor}: {round(amount, 2)}₼")

    await message.reply_text("📊 Баланс:\n" + "\n".join(lines))

async def reset_debts(message):
    cursor.execute("DELETE FROM debts")
    conn.commit()
    await message.reply_text("Все долги удалены! 🔄")

async def show_help(message):
    await message.reply_text(
        "💡 Команды:\n"
        "/add сумма описание @user1 @user2 — добавить расход\n"
        "/balance — показать баланс\n"
        "/reset — сбросить всё\n"
        "/setcard 1234567812345678 — сохранить свой номер карты\n"
        "/card @username — показать номер карты пользователя\n"
        "/report_excel — отчёт в Excel\n"
        "/help — помощь"
    )

async def send_excel_report(message):
    cursor.execute("SELECT debtor, creditor, amount FROM debts")
    rows = cursor.fetchall()
    if not rows:
        await message.reply_text("Нет данных для отчёта.")
        return

    df = pd.DataFrame(rows, columns=["Должник", "Кредитор", "Сумма"])
    excel_file = "report.xlsx"
    df.to_excel(excel_file, index=False)
    await message.reply_document(document=open(excel_file, "rb"))

# === Обработка нажатий на кнопки ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message = query.message
    data = query.data

    if data == "add":
        await message.reply_text("Введите команду вручную:\n/add 900 Ужин @user1 @user2")
    elif data == "balance":
        await show_balance(message)
    elif data == "reset":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, эээ", callback_data="confirm_reset")],
            [InlineKeyboardButton("❌ Нет, чашнулся", callback_data="cancel_reset")]
        ])
        await message.reply_text("Ты точно хочешь обнулить все расчёты? 🧨", reply_markup=keyboard)
    elif data == "confirm_reset":
        await reset_debts(message)
    elif data == "cancel_reset":
        await message.reply_text("Отмена сброса. Всё осталось как было 🤝")
    elif data == "help":
        await show_help(message)
    elif data == "excel":
        await send_excel_report(message)

# === Планировщик еженедельной напоминалки ===

# async def weekly_reminder(context: ContextTypes.DEFAULT_TYPE):
#    with open("photo_2025-06-02_15-37-57.jpg", "rb") as photo:
#        await context.bot.send_photo(
#            chat_id=CHAT_ID,
#            photo=photo,
#            caption="@CeMKuH 😎"
#        )

# async def set_weekly_job(app):
#    app.job_queue.run_daily(
#        weekly_reminder,
#        time=datetime.time(hour=11, minute=30),
#        days=(6,),
#        chat_id=CHAT_ID
#    )

# === Подключение команд ===

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("balance", lambda u, c: show_balance(u.message)))
app.add_handler(CommandHandler("reset", lambda u, c: reset_debts(u.message)))
app.add_handler(CommandHandler("help", lambda u, c: show_help(u.message)))
app.add_handler(CommandHandler("setcard", set_card))
app.add_handler(CommandHandler("card", get_card))
app.add_handler(CommandHandler("report_excel", lambda u, c: send_excel_report(u.message)))
app.add_handler(CallbackQueryHandler(button_handler))
# app.post_init = set_weekly_job # Запуск напоминалки для Семы

# === Запуск Flask-сервера для Replit ===

web_app = Flask('')

@web_app.route('/')
def home():
    return "Бот активен!"

def run_web():
    web_app.run(host='0.0.0.0', port=8080)

Thread(target=run_web).start()

print("✅ Бот запущен...")
app.run_polling()
