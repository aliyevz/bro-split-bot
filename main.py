import os
import sqlite3
import logging
import datetime
from typing import List, Any

from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    Updater,
    MessageHandler
)
import pandas as pd

import database, luhn

# Включаем логирование
logging.basicConfig(level=logging.INFO)

# Читаем токен из переменных среды
# TOKEN = "7500460303:AAEZ8XB59m5DwoOIxGK7XettnW5ekPi6tMs"
TOKEN = os.environ["BOT_TOKEN"]
# CHAT_ID = int(os.environ["CHAT_ID"])


# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type

    database.init_db(chat_id)

    if chat_type in ['group', 'supergroup', 'channel']:
        await update.message.reply_html(
            rf"Привет, {user.mention_html()}! Я бот который будет следить за расходами" 
            rf"в этом чате (**ID: `{chat_id}`**). "
        )
    else:  # Приватный чат
        await update.message.reply_html(
            rf"Привет, {user.mention_html()}! Я бот который будет следить за расходами"
        )

    keyboard = [
        [InlineKeyboardButton("➕ Добавить расход", callback_data='add')],
        [InlineKeyboardButton("➕ Добавить payback", callback_data='payback')],
        [InlineKeyboardButton("📊 Баланс братишек пиу", callback_data='balance')],
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
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
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
        batch_debts = []
        for user in involved:
            if user == payer:
                continue
            batch_debts.append((user, payer, split))

        database.add_debts_batch(chat_id, batch_debts)

        await update.message.reply_text(
            f"{description}: {amount}₼ / {len(involved)} = {split}₼\n"
            f"{', '.join('@' + u for u in involved)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Показать баланс", callback_data='balance')]
            ])
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {repr(e)}\nФормат: /add 900 Ужин @user1 @user2")



async def payback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        args = context.args
        amount = float(args[0])

        mentions = [u.lstrip('@') for u in args if u.startswith('@')]
        involved = list(set(mentions))

        if not involved:
            await update.message.reply_text("Укажи кому вернул деньги, Лебовски.")
            return

        if len(involved) > 1:
            await update.message.reply_text("Ала, бирь-бирь указывай кому вернул")
            return

        payer = update.effective_user.username or update.effective_user.first_name
        amount = round(amount / len(involved), 2)
        batch_debts = [(involved[0], payer, amount)]

        database.add_debts_batch(chat_id, batch_debts)

        await update.message.reply_text(
            f"Payback добавлен. {payer} вернул {involved[0]}  {amount}₼",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Показать баланс", callback_data='balance')]
            ])
        )
    except Exception as e:
        print(str(e))
        await update.message.reply_text(f"Ошибка: {e}\nФормат: /payback 900 @user1")


# Команда для установки / обновления карты
async def set_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        card_number = context.args[0]
        username = update.effective_user.username
        if not username:
            await update.message.reply_text("У тебя нет username в Telegram, поэтому карту сохранить нельзя.")
            return

        if len(card_number) != 16 or not card_number.isdigit():
            await update.message.reply_text("Номер карты должен быть из 16 цифр.")
            return

        if not luhn.luhn_check(card_number):
            await update.message.reply_text("Ай брааатишка, Номер карты не валидный!!!!")
            return

        database.set_card(chat_id, username, card_number)
        await update.message.reply_text("Карта успешно сохранена!")
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}\nИспользуй формат: /setcard 1234567812345678")

# Команда для просмотра карты другого пользователя
async def get_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text("Используй: /card @username")
        return

    username = context.args[0].lstrip('@')
    card = database.get_card(chat_id, username)
    if card:
        await update.message.reply_text(f"{card[0]}")
    else:
        await update.message.reply_text(f"У @{username} нет сохранённой карты.")

# === Обработчики кнопок ===

async def show_balance(message, chat_id):

    rows = database.get_debts(chat_id)
    if not rows:
        await message.reply_text("Баланс пуст — братишки рассчитались 🙌")
        return

    lines = []
    for debtor, creditor, amount in rows:
        card = database.get_card(chat_id, creditor)
        if card:
            card_info = card[0]
        else:
            card_info = "Карта не привязана"
        lines.append(f"@{debtor} должен @{creditor}: {round(amount, 2)}₼. Карта: {card_info}")

    await message.reply_text("📊 Баланс:\n" + "\n".join(lines))

async def reset_debts(message, chat_id):
    try:
        database.reset_debts(chat_id)
        await message.reply_text("Все долги удалены! 🔄")
    except Exception as e:
        await message.reply_text(repr(e))


async def show_help(message):
    await message.reply_text(
        "💡 Команды:\n"
        "/add сумма описание @user1 @user2 — добавить расход\n"
        "/payback сумма возврата @user — добавить расход\n"
        "/balance — показать баланс\n"
        "/reset — сбросить всё\n"
        "/setcard 1234567812345678 — сохранить свой номер карты\n"
        "/card @username — показать номер карты пользователя\n"
        "/report_excel — отчёт в Excel\n"
        "/help — помощь"
    )

async def send_excel_report(message, chat_id):
    rows = database.get_all_debts_report(chat_id)
    if not rows:
        await message.reply_text("Нет данных для отчёта.")
        return

    df = pd.DataFrame(rows, columns=["Дата", "Должник", "Кредитор", "Сумма"])
    excel_file = f"report-{str(chat_id)}.xlsx"
    df.to_excel(excel_file, index=False)
    await message.reply_document(document=open(excel_file, "rb"))

# === Обработка нажатий на кнопки ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    message = query.message
    data = query.data
    chat_id = query.message.chat.id

    if data == "add":
        await message.reply_text("Введите команду вручную:\n/add 900 Ужин @user1 @user2")
    elif data == "payback":
        await message.reply_text("Введите команду вручную:\n/payback 900 @user1")
    elif data == "balance":
        await show_balance(message, chat_id)
    elif data == "reset":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Да, эээ", callback_data="confirm_reset")],
            [InlineKeyboardButton("❌ Нет, чашнулся", callback_data="cancel_reset")]
        ])
        await message.reply_text("Ты точно хочешь обнулить все расчёты? 🧨", reply_markup=keyboard)
    elif data == "confirm_reset":
        await reset_debts(message, chat_id)
    elif data == "cancel_reset":
        await message.reply_text("Отмена сброса. Всё осталось как было 🤝")
    elif data == "help":
        await show_help(message)
    elif data == "excel":
        await send_excel_report(message, chat_id)


def main():
    # === Запуск Flask-сервера для Replit ===
    web_app = Flask('')

    @web_app.route('/')
    def health_check():
        return "BOT OK", 200

    # def run_web():
    #    web_app.run(host='0.0.0.0', port=8080)

    # Thread(target=run_web).start()
    def run_web():
        import os
        port = int(os.environ.get('PORT', 8080))  # Render задаёт порт через PORT
        web_app.run(host='0.0.0.0', port=port)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("payback", payback))
    app.add_handler(CommandHandler("balance", lambda u, c: show_balance(u.message, u.effective_chat.id)))
    app.add_handler(CommandHandler("reset", lambda u, c: reset_debts(u.message, u.effective_chat.id)))
    app.add_handler(CommandHandler("help", lambda u, c: show_help(u.message)))
    app.add_handler(CommandHandler("setcard", set_card))
    app.add_handler(CommandHandler("card", get_card))
    app.add_handler(CommandHandler("report_excel", lambda u, c: send_excel_report(u.message, u.effective_chat.id, c)))
    app.add_handler(CallbackQueryHandler(button_handler))
    # app.post_init = set_weekly_job # Запуск напоминалки для Семы

    Thread(target=run_web).start()

    print("✅ Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()


    

