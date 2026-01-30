import asyncio
import logging
import sys
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# Force utf-8 for windows console
sys.stdout.reconfigure(encoding='utf-8')

import config
from database import Database, User

# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# INIT
dp = Dispatcher()
bot = Bot(token=config.BOT_TOKEN)
db = Database()

# --- KEYBOARDS ---

def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="💎 Купить Premium"))
    builder.row(KeyboardButton(text="ℹ️ О боте"), KeyboardButton(text="📊 Мой статус"))
    return builder.as_markup(resize_keyboard=True)

# --- HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Received /start command from user {message.from_user.id} (@{message.from_user.username})")
    logger.info(f"Full message text: {message.text}")
    
    args = message.text.split()
    logger.info(f"Parsed args: {args}")
    
    # Check if user exists in database, create if not
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            user = User(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name
            )
            session.add(user)
            session.commit()
            logger.info(f"Created new user: {message.from_user.id}")
    finally:
        session.close()
    
    if len(args) > 1 and args[1].startswith("pay_"):
        logger.info(f"Deep link detected: {args[1]}")
        # Format: pay_premium_PERIOD_USERID (e.g. pay_premium_week_777, pay_premium_1_777)
        try:
            parts = args[1].split("_")
            logger.info(f"Deep link parts: {parts}")
            period = parts[2]  # "week", "1", "6", "12"
            user_id = int(parts[3])
            
            logger.info(f"Creating invoice for period: {period}, user_id: {user_id}")
            
            # Pricing mapping
            prices = {
                "week": {"label": "Premium 1 Неделя", "amount": 150, "days": 7},
                "1": {"label": "Premium 1 Месяц", "amount": 400, "days": 30},
                "6": {"label": "Premium 6 Месяцев", "amount": 600, "days": 180},
                "12": {"label": "Premium 1 Год", "amount": 1000, "days": 365}
            }
            
            plan = prices.get(period)
            if not plan:
                logger.error(f"Invalid period value: {period}")
                await message.answer(
                    "❌ Неверный тариф. Попробуйте снова.",
                    parse_mode=ParseMode.HTML
                )
                return

            logger.info(f"Selected plan: {plan}")

            await message.answer_invoice(
                title="💎 Premium Подписка",
                description=f"Активация Premium статуса на {plan['label']}.\n\n✨ Доступ к аналитике, прогнозам и чату!\n📊 Эксклюзивные функции\n🎯 Точные предсказания",
                payload=f"premium_{period}_{user_id}",
                provider_token="",  # Empty for Telegram Stars
                currency="XTR",  # Telegram Stars
                prices=[types.LabeledPrice(label=plan["label"], amount=plan["amount"])],
                start_parameter=f"pay_premium_{period}_{user_id}"
            )
            logger.info("Invoice sent successfully!")
            return
        except Exception as e:
            logger.error(f"Deep link error: {e}", exc_info=True)
            await message.answer(
                "❌ Ошибка при создании инвойса. Попробуйте еще раз или обратитесь к администратору.",
                parse_mode=ParseMode.HTML
            )
            return

    logger.info("Showing main menu")
    await message.answer(
        "👋 <b>Добро пожаловать в Premium Bot!</b>\n\n"
        "🌟 Этот бот предназначен для покупки Premium подписки на сайте <b>Stataggg.ru</b>\n\n"
        "💎 Выберите действие в меню:",
        reply_markup=get_main_menu(),
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "💎 Купить Premium")
async def buy_premium(message: types.Message):
    await message.answer(
        "💎 <b>Выберите тариф Premium:</b>\n\n"
        "Перейдите на сайт <a href='https://stataggg.ru'>stataggg.ru</a> и выберите тариф.\n"
        "После выбора вы автоматически вернетесь сюда для оплаты!",
        parse_mode=ParseMode.HTML
    )

@dp.message(F.text == "📊 Мой статус")
async def my_status(message: types.Message):
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
        if not user:
            await message.answer("❌ Пользователь не найден в базе данных.")
            return
        
        if user.is_premium and user.premium_until and user.premium_until > datetime.now():
            days_left = (user.premium_until - datetime.now()).days
            await message.answer(
                f"✅ <b>У вас активна Premium подписка!</b>\n\n"
                f"📅 Активна до: {user.premium_until.strftime('%d.%m.%Y')}\n"
                f"⏳ Осталось дней: {days_left}",
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer(
                "❌ <b>У вас нет активной Premium подписки</b>\n\n"
                "💎 Нажмите 'Купить Premium' для активации!",
                parse_mode=ParseMode.HTML
            )
    finally:
        session.close()

@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: types.Message):
    await message.answer(
        "ℹ️ <b>О Premium Bot</b>\n\n"
        "Этот бот предназначен для покупки Premium подписки на сайте Stataggg.ru\n\n"
        "🌐 <b>Сайт:</b> <a href='https://stataggg.ru'>stataggg.ru</a>\n"
        "👤 <b>Админ:</b> @SlavaSlavitch\n\n"
        "💎 <b>Преимущества Premium:</b>\n"
        "• Точные прогнозы матчей\n"
        "• Расширенная аналитика\n"
        "• История чата\n"
        "• Эксклюзивные функции",
        parse_mode=ParseMode.HTML
    )

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    logger.info(f"Pre-checkout query from user {pre_checkout_query.from_user.id}")
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    logger.info(f"Successful payment from user {message.from_user.id}")
    payload = message.successful_payment.invoice_payload
    logger.info(f"Payment payload: {payload}")
    
    # payload: premium_PERIOD_USERID
    parts = payload.split("_")
    period = parts[1]  # "week", "1", "6", "12"
    tg_id = int(parts[2])
    
    # Calculate actual days based on period
    days_mapping = {
        "week": 7,
        "1": 30,
        "6": 180,
        "12": 365
    }
    actual_days = days_mapping.get(period, 30)  # Default to 30 if unknown
    
    logger.info(f"Activating Premium for user {tg_id}: {actual_days} days (period: {period})")
    
    # Update user in database
    session = db.get_session()
    try:
        user = session.query(User).filter_by(telegram_id=tg_id).first()
        if not user:
            logger.error(f"User {tg_id} not found in database!")
            await message.answer("❌ Ошибка: пользователь не найден в базе данных.")
            return
        
        now = datetime.now()
        if user.is_premium and user.premium_until and user.premium_until > now:
            # Extend existing subscription
            user.premium_until += timedelta(days=actual_days)
            logger.info(f"Extended Premium until {user.premium_until}")
        else:
            # New subscription
            user.is_premium = True
            user.premium_since = now
            user.premium_until = now + timedelta(days=actual_days)
            logger.info(f"New Premium until {user.premium_until}")
        
        session.commit()
        
        await message.answer(
            f"✅ <b>Оплата успешна!</b>\n\n"
            f"💎 Premium активирован на {actual_days} дней!\n"
            f"📅 Действует до: {user.premium_until.strftime('%d.%m.%Y')}\n\n"
            f"🌐 Возвращайтесь на сайт <a href='https://stataggg.ru'>stataggg.ru</a> и наслаждайтесь всеми функциями! 🎉",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Premium activated successfully for user {tg_id}")
        
    except Exception as e:
        logger.error(f"Error activating Premium: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при активации Premium. Обратитесь к администратору."
        )
    finally:
        session.close()

# --- MAIN ---

async def main():
    logger.info("=== Premium Payment Bot Started ===")
    logger.info(f"Bot: @botproverkioplati_bot")
    
    # Create tables if they don't exist
    db.create_tables()
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
