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
            db.update_existing_users_limits()
            
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