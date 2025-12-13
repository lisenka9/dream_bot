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
import hashlib
import hmac
import signal
import handlers
from config import BOT_TOKEN, PAYPAL_WEBHOOK_ID
from database import db

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
            custom_id = resource.get('custom_id')  # Это наш user_id
            
            if payment_id and custom_id:
                # Обновляем статус платежа
                db.update_payment_status(payment_id, 'success')
                
                try:
                    user_id = int(custom_id)
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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    try:
        logger.error(f"Exception while handling an update: {context.error}")
        logger.error("Full traceback:", exc_info=context.error)
    except Exception as e:
        logger.error(f"Error in error handler itself: {e}")

def setup_handlers(application):
    """Настройка всех обработчиков команд"""
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", handlers.start))

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
    max_retries = 3
    retry_delay = 30
    
    for attempt in range(max_retries):
        # Проверяем флаг shutdown перед каждой попыткой
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
            
            # Создаем приложение
            application = Application.builder().token(BOT_TOKEN).build()
            application.add_error_handler(enhanced_error_handler)
            
            # Добавляем обработчики
            setup_handlers(application)
            
            logger.info("🚀 Starting bot polling (SINGLE INSTANCE)...")
            
            # Запускаем polling
            application.run_polling(
                poll_interval=3.0,
                timeout=20,
                drop_pending_updates=True,
                allowed_updates=['message', 'callback_query'],
                bootstrap_retries=0,
                close_loop=False
            )
            
            # Если дошли сюда, бот завершился нормально
            logger.info("✅ Bot stopped normally")
            break
            
        except Exception as e:
            error_str = str(e)
            if "Conflict" in error_str:
                logger.error(f"💥 CONFLICT DETECTED on attempt {attempt + 1}: {e}")
                logger.info("🔄 This usually means another instance is running. Waiting...")
            else:
                logger.error(f"❌ Bot crashed on attempt {attempt + 1}: {e}")
            
            if attempt < max_retries - 1 and not shutdown_manager.shutdown_event.is_set():
                current_delay = min(retry_delay * (2 ** attempt), 300)
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
        # Запускаем Flask в отдельном потоке
        flask_thread = threading.Thread(target=run_flask_server, daemon=True)
        flask_thread.start()
        logger.info("✅ Flask server started in thread")
        
        # Даем Flask время на запуск
        time.sleep(3)
        
        # Запускаем самопинг в отдельном потоке
        ping_thread = threading.Thread(target=ping_self, daemon=True)
        ping_thread.start()
        logger.info("✅ Self-ping started")

        # Запускаем бота в ОСНОВНОМ потоке
        logger.info("✅ Starting bot in main thread...")
        run_bot()
        
    except Exception as e:
        logger.error(f"💥 Error in main: {e}")
    finally:
        logger.info("🛑 Bot application stopped")

if __name__ == '__main__':
    main()