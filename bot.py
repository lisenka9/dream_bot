import logging
import os
import time
import json
import requests
import threading
from flask import Flask, request, jsonify, redirect, Response, stream_with_context
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import multiprocessing
import sys
from datetime import datetime, timedelta
from telegram import Update
import asyncio
import signal
import handlers
from config import BOT_TOKEN, PAYPAL_WEBHOOK_ID
from database import db

class CourseScheduler:
    """Планировщик для отправки ежедневных сообщений курса"""
    
    def __init__(self, application):
        self.application = application
        self.db = db
        self.running = False
        
    def start(self):
        """Запускает планировщик"""
        self.running = True
        thread = threading.Thread(target=self._run_scheduler, daemon=True)
        thread.start()
        logger.info("✅ Course scheduler started")
    
    def _run_scheduler(self):
        """Запускает цикл планировщика"""
        while self.running:
            try:
                self.check_and_send_messages()
                time.sleep(60)  # Проверяем каждую минуту
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}")
                time.sleep(300)  # При ошибке ждем 5 минут
    
    def check_and_send_messages(self):
        """Проверяет и отправляет сообщения пользователям"""
        try:
            conn = self.db.get_connection()
            if not conn:
                return
            
            cursor = conn.cursor()
            
            # ИСПРАВЛЕННЫЙ ЗАПРОС: используем last_message_date вместо last_message_time
            cursor.execute('''
                SELECT user_id, current_day 
                FROM course_progress 
                WHERE is_active = TRUE 
                AND current_day <= 7
                AND (
                    last_message_date IS NULL 
                    OR last_message_date <= NOW() - INTERVAL '23 hours 55 minutes'
                )
            ''')
            
            users = cursor.fetchall()
            conn.close()
            
            for user_id, current_day in users:
                try:
                    logger.info(f"📨 Sending day {current_day} to user {user_id}")
                    
                    # Отправляем сообщения дня
                    if self.application.bot:
                        asyncio.run_coroutine_threadsafe(
                            self.send_course_day(user_id, current_day),
                            self.application.bot._loop
                        )
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.error(f"❌ Error scheduling for user {user_id}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in check_and_send_messages: {e}")
    
    async def send_course_day(self, user_id: int, day_number: int):
        """Отправляет сообщения конкретного дня по правильной структуре"""
        try:
            # Получаем контент дня
            content = self.db.get_course_content(day_number)
            if not content:
                logger.error(f"❌ No content for day {day_number}")
                return
            
            messages = content['messages']
            has_images = content['has_images']
            image_urls = content.get('image_urls', [])
            
            image_index = 0  # Индекс для картинок
            
            # Отправляем каждое сообщение по порядку
            for i, message in enumerate(messages):
                if message.strip():  # Если сообщение не пустое
                    try:
                        # ИСПРАВЬТЕ ЭТУ ЧАСТЬ: добавьте конвертацию в HTML
                        from database import DatabaseManager
                        html_message = DatabaseManager.markdown_to_html(message)
                        
                        await self.application.bot.send_message(
                            chat_id=user_id,
                            text=html_message,
                            parse_mode='HTML'  # Используем HTML вместо Markdown
                        )
                        await asyncio.sleep(1)  # Задержка 1 секунда между сообщениями
                    except Exception as e:
                        logger.error(f"Error sending message {i+1} to {user_id}: {e}")
                        # Попробуем отправить без разметки
                        try:
                            await self.application.bot.send_message(
                                chat_id=user_id,
                                text=message,
                                parse_mode=None
                            )
                        except:
                            pass
                
                # Если это пустое сообщение и есть картинки, отправляем картинку
                elif has_images and image_index < len(image_urls):
                    try:
                        await self.application.bot.send_photo(
                            chat_id=user_id,
                            photo=image_urls[image_index]
                        )
                        await asyncio.sleep(1)
                        image_index += 1
                    except Exception as e:
                        logger.error(f"Error sending image {image_index} to {user_id}: {e}")
            
            # Обновляем прогресс пользователя
            self.update_user_progress(user_id, day_number)
            
            logger.info(f"✅ Day {day_number} sent to user {user_id}")
            
            # Если это день 7, отправляем предложение марафона
            if day_number == 7:
                await self.send_marathon_offer(user_id)
                
        except Exception as e:
            logger.error(f"❌ Error in send_course_day: {e}")

    def update_user_progress(self, user_id: int, current_day: int):
        """Обновляет прогресс пользователя - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
        conn = self.db.get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            
            if current_day < 7:
                # Переходим к следующему дню
                next_day = current_day + 1
                cursor.execute('''
                    UPDATE course_progress 
                    SET current_day = %s, 
                        last_message_date = NOW(),  -- Используем last_message_date
                        is_active = TRUE
                    WHERE user_id = %s
                ''', (next_day, user_id))
            else:
                # Завершаем курс
                cursor.execute('''
                    UPDATE course_progress 
                    SET is_active = FALSE,
                        completed_at = NOW(),
                        last_message_date = NOW()  -- Используем last_message_date
                    WHERE user_id = %s
                ''', (user_id,))
            
            conn.commit()
            logger.info(f"✅ Progress updated for user {user_id}: day {current_day}")
            
        except Exception as e:
            logger.error(f"❌ Error updating progress: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    async def send_marathon_offer(self, user_id: int):
        """Отправляет предложение марафона после завершения курса"""
        try:
            from telegram import InlineKeyboardMarkup, InlineKeyboardButton
            
            marathon_text = """
🔥 **Поздравляю с завершением 7-дневного пути!**

Вы прошли весь цикл: от мечты до плана. Вы уже знаете, как ставить цели и создавать **движение.** Готовы ли вы закрепить этот навык и **реализовать цели под руководством психотерапевта?**

Приглашаю вас на большой **Марафон «От мечты к цели»,** где мы проведем 21 день в глубокой работе над вашими планами, устраняя блоки и страхи.

✨ **Что вас ждет:**
✔️**3 недели** структурированной работы в **групповом чате Telegram.**
✔️**Взаимообмен и переопыление** с другими участниками для мощной поддержки.
✔️Моя персональная поддержка.
✔️Глубокая проработка **блоков и страхов.**
✔️Закрепление навыка достижения цели до результата.

🎁🎁 **Специальный Бонус для вас!**
Вместо 7000₽, вы получаете Марафон всего за **4900₽!**

🗓️ **Старт Марафона: 4 января 2026 года.**
Узнать подробности и оплатить со скидкой👇
"""
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📖 Узнать подробности марафона", callback_data="marathon_info")],
                [InlineKeyboardButton("💳 Оплатить марафон", callback_data="marathon_payment")]
            ])
            
            await self.application.bot.send_message(
                chat_id=user_id,
                text=marathon_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Error sending marathon offer: {e}")


class GracefulShutdown:
    def __init__(self):
        self.shutdown_event = threading.Event()
        
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"🛑 Received shutdown signal {signum}. Starting graceful shutdown...")
        self.shutdown_event.set()
        
        # Уведомляем администраторов
        self.notify_admins_about_shutdown(signum)
    
    def notify_admins_about_shutdown(self, signum):
        """Уведомляет администраторов о shutdown"""
        try:
            from telegram import Bot
            from config import BOT_TOKEN, ADMIN_IDS
            
            bot = Bot(token=BOT_TOKEN)
            message = f"🛑 Bot received shutdown signal {signum} at {datetime.now()}"
            
            for admin_id in ADMIN_IDS:
                try:
                    bot.send_message(chat_id=admin_id, text=message)
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
        except Exception as e:
            logger.error(f"Could not send shutdown notification: {e}")

shutdown_manager = GracefulShutdown()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/')
def home():
    return "Dream Bot is running!"

@app.route('/health')
def health_check():
    return "✅ Bot is alive!", 200

@app.route('/webhook/yookassa', methods=['POST'])
def yookassa_webhook():
    """Вебхук от ЮKassa с реальной проверкой"""
    try:
        # Получаем подпись
        signature = request.headers.get('Content-Signature', '')
        
        # Проверяем подпись
        is_valid = payment_processor.verify_yookassa_webhook(
            request.get_data(),
            signature
        )
        
        if not is_valid:
            logger.warning("⚠️ Invalid YooKassa webhook signature")
            return 'Invalid signature', 400
        
        data = request.get_json()
        event = data.get('event')
        payment_id = data.get('object', {}).get('id')
        
        logger.info(f"📥 YooKassa webhook received: {event} for payment {payment_id}")
        
        if event == 'payment.succeeded':
            # Обновляем статус в БД
            user_id = db.update_payment_status(payment_id, 'success')
            
            if user_id:
                logger.info(f"✅ Payment {payment_id} succeeded for user {user_id}")
                
                from payment_processor import PaymentProcessor
                payment_processor = PaymentProcessor(db)
                payment_processor.notify_admin({
                    'user_id': user_id,
                    'payment_id': payment_id,
                    'amount': 599.00,
                    'currency': "RUB",
                    'payment_method': "yookassa"
                })

                # Немедленно активируем курс
                from handlers import activate_course_after_payment
                
                # Получаем application из контекста
                if telegram_app:
                    # Запускаем в отдельном потоке
                    import threading
                    thread = threading.Thread(
                        target=lambda: asyncio.run(
                            activate_course_after_payment(user_id, payment_id, telegram_app)
                        )
                    )
                    thread.start()
                    
                    logger.info(f"🚀 Course activation started for user {user_id}")
                else:
                    logger.error("❌ Telegram app not initialized")
            
            return 'OK', 200
            
        elif event == 'payment.canceled':
            db.update_payment_status(payment_id, 'canceled')
            logger.info(f"❌ Payment {payment_id} canceled")
            return 'OK', 200
            
        elif event == 'payment.waiting_for_capture':
            db.update_payment_status(payment_id, 'pending')
            logger.info(f"⏳ Payment {payment_id} waiting for capture")
            return 'OK', 200
            
    except Exception as e:
        logger.error(f"❌ YooKassa webhook error: {e}")
        return 'Error', 500

@app.route('/webhook/paypal', methods=['POST'])
def paypal_webhook():
    """Вебхук от PayPal с проверкой"""
    try:
        # Проверяем вебхук
        is_valid = payment_processor.verify_paypal_webhook(
            request.get_data(),
            request.headers
        )
        
        if not is_valid:
            logger.warning("⚠️ Invalid PayPal webhook signature")
            return 'Invalid signature', 400
        
        data = request.get_json()
        event_type = data.get('event_type')
        resource = data.get('resource', {})
        
        logger.info(f"📥 PayPal webhook: {event_type}")
        
        if event_type == 'PAYMENT.CAPTURE.COMPLETED':
            payment_id = resource.get('id')
            custom_id = resource.get('custom_id')  
            
            if payment_id and custom_id:
                # Обновляем статус платежа
                db.update_payment_status(payment_id, 'success')
                
                try:
                    user_id = int(custom_id)

                    from payment_processor import PaymentProcessor
                    payment_processor = PaymentProcessor(db)
                    payment_processor.notify_admin({
                        'user_id': user_id,
                        'payment_id': payment_id,
                        'amount': 30.00,
                        'currency': "ILS",
                        'payment_method': "paypal"
                    })

                    # Активируем курс
                    from handlers import activate_course_after_payment
                    
                    if telegram_app:
                        import threading
                        thread = threading.Thread(
                            target=lambda: asyncio.run(
                                activate_course_after_payment(user_id, payment_id, telegram_app)
                            )
                        )
                        thread.start()
                        logger.info(f"✅ PayPal payment {payment_id} activated for user {user_id}")
                        
                except ValueError as e:
                    logger.error(f"❌ Invalid user_id in PayPal webhook: {custom_id}")
        
        return 'OK', 200
        
    except Exception as e:
        logger.error(f"❌ PayPal webhook error: {e}")
        return 'Error', 500

def activate_course_thread(user_id: int, payment_id: str):
    """Активирует курс в отдельном потоке"""
    try:
        from handlers import activate_course_after_payment
        
        # Создаем event loop для асинхронной функции
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Запускаем активацию курса
        loop.run_until_complete(
            activate_course_after_payment(user_id, payment_id, telegram_app)
        )
        
        loop.close()
        
    except Exception as e:
        logger.error(f"Error in activation thread: {e}")

def ping_self():
    """Пингует собственный health endpoint"""
    service_url = os.environ.get('RENDER_EXTERNAL_URL')
    
    while True:
        try:
            response = requests.get(f"{service_url}/health", timeout=10)
            logger.info(f"✅ Self-ping successful: {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Self-ping failed: {e}")
        
        # Ждем 10 минут (600 секунд)
        time.sleep(600)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок в хендлерах"""
    try:
        error = context.error
        
        # Логируем ошибку
        logging.error(f"Exception while handling an update: {context.error}")
        
        # Пытаемся отправить пользователю сообщение об ошибке
        try:
            if update and update.effective_chat:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ Произошла техническая ошибка. Попробуйте позже."
                )
        except:
            pass
            
    except Exception as e:
        logging.error(f"Error in error handler: {e}")

def setup_handlers(application):
    """Настройка всех обработчиков команд"""
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("activate_course", handlers.activate_course_command))
    application.add_handler(CommandHandler("stats", handlers.stats_command))
    application.add_handler(CommandHandler("check_user", handlers.check_user_command))
    application.add_handler(CommandHandler("reset_course", handlers.reset_course_command))
    application.add_handler(CommandHandler("check_content", handlers.check_content_command))
    application.add_handler(CommandHandler("recreate_content", handlers.recreate_content_command))
    application.add_handler(CommandHandler("test_simple", handlers.test_simple_command))
    application.add_handler(CommandHandler("debug_content", handlers.debug_content_command))
    application.add_handler(CommandHandler("test_markdown", handlers.test_markdown_command))

    application.add_handler(CallbackQueryHandler(handlers.button_handler))

async def enhanced_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Улучшенный обработчик ошибок с обработкой конфликтов"""
    try:
        error = context.error
        
        # Обрабатываем конфликты отдельно
        if isinstance(error, Exception) and "Conflict" in str(error):
            logger.error("💥 CONFLICT: Multiple bot instances detected!")
            logger.info("🔄 Waiting before restart...")
            # Не логируем полный traceback для конфликтов
            return
        
        # Логируем другие ошибки
        logger.error(f"Exception while handling an update: {error}")
        logger.error("Full traceback:", exc_info=error)
        
    except Exception as e:
        logger.error(f"Error in enhanced error handler: {e}")

def run_bot():
    """Запускает бота в основном потоке"""
    max_retries = 5
    retry_delay = 30
    
    for attempt in range(max_retries):
        if shutdown_manager.shutdown_event.is_set():
            logger.info("🛑 Shutdown detected, stopping bot")
            return
            
        try:
            logger.info(f"🔄 Attempt {attempt + 1} to start bot...")
            
            if not BOT_TOKEN:
                logger.error("❌ BOT_TOKEN not found in environment variables!")
                time.sleep(retry_delay)
                continue
            
            # Инициализация базы данных
            logger.info("🔄 Initializing database...")
            db.init_database()
            
            # Создаем приложение с улучшенными настройками
            application = Application.builder().token(BOT_TOKEN).build()
            
            # Добавляем обработчик ошибок
            application.add_error_handler(error_handler)
            
            # Добавляем обработчики команд
            setup_handlers(application)
            
            logger.info("🚀 Starting bot polling...")
            
            # Запускаем polling с улучшенными настройками
            application.run_polling(
                poll_interval=5.0,  # Увеличили интервал
                timeout=30,
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query'],
                bootstrap_retries=3,  # Добавили повторные попытки при запуске
                close_loop=False
            )
            
            logger.info("✅ Bot stopped normally")
            break
            
        except Exception as e:
            error_str = str(e)
            if "Conflict" in error_str:
                logger.error(f"💥 CONFLICT DETECTED on attempt {attempt + 1}: {e}")
                logger.info("🔄 This usually means another instance is running. Waiting...")
            elif "Connection" in error_str or "Network" in error_str:
                logger.error(f"🌐 NETWORK ERROR on attempt {attempt + 1}: {e}")
            else:
                logger.error(f"❌ Bot crashed on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1 and not shutdown_manager.shutdown_event.is_set():
                current_delay = min(retry_delay * (2 ** attempt), 300)  # Экспоненциальная задержка
                logger.info(f"🔄 Restarting in {current_delay} seconds...")
                for _ in range(current_delay):
                    if shutdown_manager.shutdown_event.is_set():
                        return
                    time.sleep(1)
            else:
                logger.error("💥 Max retries exceeded or shutdown requested")
                if not shutdown_manager.shutdown_event.is_set():
                    raise

def run_flask_server():
    """Запускает Flask сервер"""
    try:
        port = int(os.environ.get("PORT", 10000))
        logger.info(f"🚀 Starting Flask server on port {port}")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"❌ Flask server crashed: {e}")

def signal_handler(signum, frame):
    """Обработчик сигналов для graceful shutdown"""
    logger.info("🛑 Received shutdown signal. Stopping bot gracefully...")

def main():
    """Основная функция запуска - ТОЛЬКО ОДИН ПРОЦЕСС"""
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, shutdown_manager.signal_handler)
    signal.signal(signal.SIGTERM, shutdown_manager.signal_handler)
    
    logger.info("🚀 Starting Metaphor Bot (SINGLE INSTANCE)...")
    
    try:
        logger.info("🔄 Initializing database...")
        db.init_database()
        logger.info("🔄 Initializing course content...")
        db.initialize_course_content()

        flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        flask_thread.start()
        logger.info("✅ Flask server started in thread")
        
        # Даем Flask время на запуск
        time.sleep(3)
        
        # Запускаем самопинг
        ping_thread = threading.Thread(target=ping_self, daemon=True)
        ping_thread.start()
        logger.info("✅ Self-ping started")

        # Создаем приложение бота
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Сохраняем глобально для вебхуков
        global telegram_app
        telegram_app = application
        
        # Настраиваем обработчики
        setup_handlers(application)
        
        # Запускаем планировщик курса
        scheduler = CourseScheduler(application)
        scheduler.start()
        logger.info("✅ Course scheduler started")
        
        # Запускаем бота
        logger.info("🚀 Starting bot polling...")
        application.run_polling(
            poll_interval=3.0,
            timeout=20,
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query'],
            bootstrap_retries=0,
            close_loop=False
        )
        
    except Exception as e:
        logger.error(f"💥 Error in main: {e}")
        import traceback
        traceback.print_exc()  # Выводим полный traceback
    finally:
        logger.info("🛑 Bot application stopped")

if __name__ == '__main__':
    main()