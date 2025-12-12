import logging
import asyncio
from telegram import Bot
from database import db
from config import BOT_TOKEN
from datetime import datetime

logger = logging.getLogger(__name__)

async def send_daily_messages():
    """Основная функция для отправки ежедневных сообщений"""
    logger.info("🔄 Starting daily messages check...")
    
    # Получаем пользователей, которым нужно отправить сообщения
    users = db.get_users_for_daily_messages()
    logger.info(f"📋 Found {len(users)} users for daily messages")
    
    if not users:
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    for user_id, current_day in users:
        try:
            # Получаем контент для текущего дня
            content = db.get_course_content(current_day)
            if not content:
                logger.error(f"❌ No content found for day {current_day}")
                continue
            
            # Отправляем все сообщения дня
            for message_data in content:
                await send_message(bot, user_id, message_data)
                await asyncio.sleep(1)  # Небольшая задержка между сообщениями
            
            # Обновляем прогресс пользователя
            db.update_user_progress(user_id, current_day)
            logger.info(f"✅ Sent day {current_day} messages to user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Error sending messages to user {user_id}: {e}")

async def send_message(bot, user_id, message_data):
    """Отправляет одно сообщение пользователю"""
    try:
        if message_data['type'] == 'text':
            await bot.send_message(
                chat_id=user_id,
                text=message_data['content'],
                parse_mode='Markdown'
            )
        elif message_data['type'] == 'photo':
            await bot.send_photo(
                chat_id=user_id,
                photo=message_data['content']
            )
        # Можно добавить другие типы: document, audio, video и т.д.
    except Exception as e:
        logger.error(f"❌ Error sending message to {user_id}: {e}")
        raise