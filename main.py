from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
import datetime
import json
import os

# توکن ربات
TOKEN = "8252798755:AAFN7qdy1M3Eq_HELjhy6svTR2dmomJLqRU"

# فایل برای ذخیره نوبت‌ها
APPOINTMENTS_FILE = "appointments.json"

# بازه‌های زمانی مجاز (۹:۰۰ تا ۱۳:۰۰ و ۱۶:۰۰ تا ۲۰:۰۰، با فاصله ۴۵ دقیقه)
TIME_SLOTS = [
    "09:00", "09:45", "10:30", "11:15", "12:00", "12:45",
    "16:00", "16:45", "17:30", "18:15", "19:00", "19:45"
]

# بارگذاری نوبت‌ها از فایل
def load_appointments():
    if os.path.exists(APPOINTMENTS_FILE):
        with open(APPOINTMENTS_FILE, "r") as f:
            return json.load(f)
    return {}

# ذخیره نوبت‌ها در فایل
def save_appointments(appointments):
    with open(APPOINTMENTS_FILE, "w") as f:
        json.dump(appointments, f)

appointments = load_appointments()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📅 ثبت نوبت", callback_data='book')],
        [InlineKeyboardButton("❌ لغو نوبت", callback_data='cancel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "به ربات نوبت‌دهی پزشکی خوش اومدی! 🩺\nلطفاً یکی از گزینه‌ها رو انتخاب کن:",
        reply_markup=reply_markup
    )

async def book(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "لطفاً تاریخ نوبت رو به شکل 'YYYY-MM-DD' وارد کن (مثال: 2025-10-05)"
    )
    context.user_data['awaiting_date'] = True

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    if user_id in appointments and appointments[user_id]:
        keyboard = [
            [InlineKeyboardButton(f"{appt['time']} - {appt['phone']}", callback_data=f'cancel_{i}')]
            for i, appt in enumerate(appointments[user_id])
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("کدام نوبت رو می‌خوای لغو کنی؟", reply_markup=reply_markup)
    else:
        await query.message.reply_text("شما هیچ نوبت ثبت‌شده‌ای ندارید!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text

    if context.user_data.get('awaiting_date', False):
        try:
            appt_date = datetime.datetime.strptime(text, '%Y-%m-%d')
            if appt_date.date() < datetime.datetime.now().date():
                await update.message.reply_text("نمی‌تونی نوبت برای تاریخ گذشته رزرو کنی!")
                return
            context.user_data['date'] = text
            context.user_data['awaiting_date'] = False
            context.user_data['awaiting_time'] = True
            
            # ایجاد دکمه‌ها برای بازه‌های زمانی
            keyboard = [
                [InlineKeyboardButton(slot, callback_data=f"time_{slot}")]
                for slot in TIME_SLOTS
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "لطفاً یکی از بازه‌های زمانی رو انتخاب کن:",
                reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text("فرمت تاریخ اشتباهه! لطفاً به شکل 'YYYY-MM-DD' وارد کن.")
    
    elif context.user_data.get('awaiting_phone', False):
        if not text.isdigit() or len(text) < 10:
            await update.message.reply_text("شماره همراه معتبر نیست! لطفاً یه شماره معتبر (مثل 09123456789) وارد کن.")
            return
        context.user_data['phone'] = text
        context.user_data['awaiting_phone'] = False

        # ثبت نوبت
        appt_time = context.user_data['time']
        appt_date = context.user_data['date']
        if user_id not in appointments:
            appointments[user_id] = []
        appointments[user_id].append({"time": f"{appt_date} {appt_time}", "phone": text})
        save_appointments(appointments)
        await update.message.reply_text(
            f"نوبت شما برای {appt_date} ساعت {appt_time} با شماره {text} ثبت شد! ✅"
        )
        context.user_data.clear()

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    data = query.data

    if data == 'book':
        await book(update, context)
    elif data == 'cancel':
        await cancel(update, context)
    elif data.startswith('time_'):
        time_slot = data.split('_')[1]
        if time_slot not in TIME_SLOTS:
            await query.message.reply_text("بازه زمانی نامعتبره!")
            return
        context.user_data['time'] = time_slot
        context.user_data['awaiting_time'] = False
        context.user_data['awaiting_phone'] = True
        await query.message.reply_text("لطفاً شماره همراه خودتون رو وارد کنید (مثل 09123456789):")
    elif data.startswith('cancel_'):
        index = int(data.split('_')[1])
        if user_id in appointments and index < len(appointments[user_id]):
            removed = appointments[user_id].pop(index)
            save_appointments(appointments)
            await query.message.reply_text(f"نوبت '{removed['time']}' با شماره {removed['phone']} لغو شد. ❌")
            if not appointments[user_id]:
                del appointments[user_id]
        else:
            await query.message.reply_text("نوبت نامعتبره!")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
