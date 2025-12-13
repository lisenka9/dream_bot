from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
import logging
import csv
import io
from datetime import datetime, date
import uuid
import json
import asyncio
from payment_processor import PaymentProcessor
from database import db 
from config import ADMIN_IDS
import keyboard

payment_processor = PaymentProcessor(db)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()
    logging.info(f"🔧 DEBUG: button_handler called with: {query.data}")
    
    # ✅ Защита от множественных нажатий
    user_id = query.from_user.id
    current_time = datetime.now().timestamp()
    
    if 'last_button_click' in context.user_data:
        last_click = context.user_data['last_button_click']
        if current_time - last_click < 1:  # 1 секунды между нажатиями
            logging.info(f"⚡ Fast click protection for user {user_id}")
            return
    
    context.user_data['last_button_click'] = current_time
    
    # ✅ Логируем какая кнопка нажата
    logging.info(f"🔄 Button pressed: {query.data} by user {user_id}")
    
    if query.data == "payment_yookassa":
        await show_yookassa_initial(query, context)
    
    elif query.data == "payment_paypal":
        await show_paypal_initial(query, context)
    
    elif query.data == "process_yookassa_payment":
        await create_yookassa_payment(query, context)
    
    elif query.data == "process_paypal_payment":
        await create_paypal_payment(query, context)
    
    elif query.data.startswith("check_yookassa_"):
        await check_specific_payment(query, context, "yookassa")
    
    elif query.data.startswith("check_paypal_"):
        await check_specific_payment(query, context, "paypal")
    
    elif query.data == "back_to_payment_method":
        await back_to_payment_methods(query, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    logging.info(f"New user: ID={user.id}, Name={user.first_name}, "
                 f"Username=@{user.username}, LastName={user.last_name}")
    try:
        db.get_or_create_user(
            user_id=user.id,
            username=user.username or "",  
            first_name=user.first_name or "",  
            last_name=user.last_name or ""  
        )
    except Exception as e:
        logging.error(f"Database error in /start: {e}")
        # Можно отправить пользователю сообщение об ошибке
        await update.message.reply_text("⚠️ Технические неполадки. Попробуйте позже.")
        return
    
    if user.first_name:
        greeting = f"🌟 Здравствуйте, {user.first_name}! 🌟"
    else:
        greeting = f"🌟 Здравствуйте, @{user.username}! 🌟"
    
    try:
        short_caption = f"""{greeting} Рада видеть вас на курсе "**Путь к мечте. Пошаговая инструкция!**"

Меня зовут **Светлана Скромова** — я дипломированный психотерапевт.

Это 7-дневный курс в формате бота. **В течение 7 дней вы будете получать по одному сообщению с заданием 1 раз в сутки**.

Цель этого пути: дать вам четкий пошаговый план, чтобы превратить вашу **мечту** в **конкретную, реальную цель**!

За эти 7 дней вы:
💫 Соприкоснетесь со своими **истинными желаниями** (а не навязанными).
✅ Правильно сформулируете их и превратите в конкретные **цели**.
🚀 Создадите **мощное вдохновение** для их реализации через практические техники.

Курс рассчитан на самостоятельную, но очень увлекательную работу!
        """
        await update.message.reply_text(
            short_caption,
            parse_mode='Markdown'
        )
        
        welcome_text_1 = f"""    
💡 Главный Секрет Исполнения Желаний:

Я заметила простую закономерность: у людей, которые **умеют мечтать** и прикладывают **определенные усилия**, желания действительно сбываются! 🚀

Многие, кто составлял списки желаний, спустя годы с удивлением обнаруживали, что почти **всё исполнилось**!

Здесь сработало правило: **четко сформулировать желание, отпустить запрос во Вселенную и ориентироваться на конечный результат.**
        """
        await update.message.reply_text(
            welcome_text_1,
            parse_mode='Markdown'
        )
        
        welcome_text_2 = f"""
🙏 Важная Составляющая: ВЕРА!

Секрет не только в формулировке, но и в **искренней вере** в успех. А также — в **приложении действий** для реализации мечты.

⚠️ Если вы полны скептицизма и пришли, чтобы сказать "это не работает" — наш путь разойдется. Курс для тех, кто готов верить и действовать.

✨ Вы готовы открыть свой "**Путь к мечте**" и работать над собой следующие 7 дней?
        """
        await update.message.reply_text(
            welcome_text_2,
            parse_mode='Markdown'
        )
        
        welcome_text_3 = f"""
🚀 Запускаем Путешествие!

Вы уже познакомились со мной и узнали главную идею курса. Если вы согласны с принципами и готовы к серьезной работе — мы начинаем прямо сейчас.

✅ **Стоимость 7-дневного курса всего 599 рублей или 30 шекелей.**

Доступ к материалам (7 дней контента, доступ на 14 дней) откроется сразу после оплаты.

Выберите способ оплаты:

🇷🇺 *Оплата из России* (рубли)
🌍 *Оплата из любой точки мира* (шекели)

Обе системы обеспечивают безопасную оплату и мгновенную активацию подписки.
"""
        await update.message.reply_text(
            welcome_text_3,
            reply_markup=keyboard.get_payment_method_keyboard(),
            parse_mode='Markdown'
        )
    
    except Exception as e:
        logging.error(f"❌ Error in start handler: {e}")

async def show_payment_method(query, context: ContextTypes.DEFAULT_TYPE, method: str):
    """Показывает информацию о способе оплаты"""
    if method == "yookassa":
        text = """
💳 *Оплата из России*
✅ *Стоимость:* 599 рублей
Нажмите кнопку *«Оплатить 599₽»* для перехода к оплате.
После успешной оплаты доступ к курсу откроется автоматически в течение 1-2 минут.
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить 599₽", callback_data="process_yookassa")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_methods")]
        ])
    else:  # paypal
        text = """
💳 *Оплата из любой точки мира*
✅ *Стоимость:* 30 шекелей 
Нажмите кнопку *«Оплатить 30₪»* для перехода к оплате.
После успешной оплаты доступ к курсу откроется автоматически в течение 1-2 минут.
"""
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Оплатить 30₪", callback_data="process_paypal")],
            [InlineKeyboardButton("◀️ Назад", callback_data="back_to_methods")]
        ])
    
    await query.edit_message_text(text=text, reply_markup=keyboard, parse_mode='Markdown')

async def show_yookassa_initial(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает первый экран с кнопкой оплаты для ЮKassa"""
    payment_text = """
💳 *Оплата из России*
✅ *Стоимость:* 599 рублей

Нажмите кнопку *«Оплатить 599₽»* для перехода к оплате.

После успешной оплаты доступ к курсу откроется автоматически в течение 1-2 минут.
"""
    
    # Отправляем НОВОЕ сообщение, не редактируем старое
    await query.message.reply_text(
        payment_text,
        reply_markup=keyboard.get_yookassa_initial_keyboard(),
        parse_mode='Markdown'
    )

async def show_paypal_initial(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает первый экран с кнопкой оплаты для PayPal"""
    payment_text = """
💳 *Оплата из любой точки мира*
✅ *Стоимость:* 30 шекелей (₪)

Нажмите кнопку *«Оплатить 30₪»* для перехода к оплате.

После успешной оплаты доступ к курсу откроется автоматически в течение 1-2 минут.
"""
    
    # Отправляем НОВОЕ сообщение
    await query.message.reply_text(
        payment_text,
        reply_markup=keyboard.get_paypal_initial_keyboard(),
        parse_mode='Markdown'
    )

async def create_yookassa_payment(query, context: ContextTypes.DEFAULT_TYPE):
    """Создает платеж ЮKassa и показывает ссылку"""
    user_id = query.from_user.id
    
    # Создаем платеж
    payment_url, payment_id = payment_processor.create_yookassa_payment(user_id)
    
    if payment_url:
        # Сохраняем payment_id для проверки
        context.user_data['last_payment_id'] = payment_id
        
        payment_text = f"""
✅ *Платеж создан!*

💳 *Оплата через ЮKassa*
✅ *Стоимость:* 599 рублей

Нажмите кнопку ниже для перехода к оплате.

После успешной оплаты доступ откроется автоматически в течение 1-2 минут.

🆔 *ID платежа:* `{payment_id}`
        """
        
        # Отправляем НОВОЕ сообщение с ссылкой
        await query.message.reply_text(
            payment_text,
            reply_markup=keyboard.get_yookassa_payment_keyboard(payment_url, payment_id),
            parse_mode='Markdown'
        )
    else:
        await query.answer("❌ Ошибка создания платежа", show_alert=True)

async def create_paypal_payment(query, context: ContextTypes.DEFAULT_TYPE):
    """Создает платеж PayPal и показывает ссылку"""
    user_id = query.from_user.id
    
    # Создаем платеж
    payment_url, payment_id = payment_processor.create_paypal_payment(user_id)
    
    if payment_url:
        # Сохраняем payment_id для проверки
        context.user_data['last_payment_id'] = payment_id
        
        payment_text = f"""
✅ *Платеж создан!*

💳 *Оплата через PayPal*
✅ *Стоимость:* 30 шекелей (₪)

Нажмите кнопку ниже для перехода к оплате.

После успешной оплаты доступ откроется автоматически в течение 1-2 минут.

🆔 *ID платежа:* `{payment_id}`
        """
        
        # Отправляем НОВОЕ сообщение с ссылкой
        await query.message.reply_text(
            payment_text,
            reply_markup=keyboard.get_paypal_payment_keyboard(payment_url, payment_id),
            parse_mode='Markdown'
        )
    else:
        await query.answer("❌ Ошибка создания платежа", show_alert=True)

async def check_specific_payment(query, context: ContextTypes.DEFAULT_TYPE, method: str):
    """Проверяет конкретный платеж"""
    # Извлекаем payment_id из callback_data
    payment_id = query.data.replace(f"check_{method}_", "")
    
    # Проверяем статус платежа
    status = payment_processor.check_payment_status(payment_id)
    
    if status == "success":
        # Активируем курс
        await activate_course_after_payment(
            query.from_user.id,
            payment_id,
            method,
            context.application
        )
        
        # Удаляем сообщение с кнопкой проверки
        try:
            await query.delete_message()
        except:
            pass
            
    elif status == "pending":
        await query.answer(
            "⏳ Платеж еще обрабатывается. Попробуйте через 2 минуты.",
            show_alert=True
        )
    else:
        await query.answer(
            "❌ Платеж не найден или отменен",
            show_alert=True
        )

async def activate_course_after_payment(user_id: int, payment_id: str, method: str, application):
    """Активирует курс после успешной оплаты"""
    try:
        # Отправляем сообщение об успешной оплате
        await application.bot.send_message(
            chat_id=user_id,
            text="""✅ *Оплата прошла успешно!*

🎉 Доступ к курсу «Путь к мечте» активирован!

Первое задание уже ждет вас ниже ⬇️""",
            parse_mode='Markdown'
        )
        
        # Отправляем День 1
        await send_course_day1(user_id, application)
        
        # Уведомляем администратора
        payment_processor.notify_admin({
            'user_id': user_id,
            'payment_id': payment_id,
            'amount': 599.00 if method == "yookassa" else 30.00,
            'currency': "RUB" if method == "yookassa" else "ILS",
            'payment_method': method
        })
        
        # Запускаем отправку остальных дней
        from bot import schedule_course_messages
        await schedule_course_messages(user_id, application)
        
    except Exception as e:
        logging.error(f"❌ Error activating course: {e}")

async def back_to_payment_methods(query, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору метода оплаты"""
    back_text = """
🚀 Выберите способ оплаты:

🇷🇺 *Оплата из России* (рубли)
🌍 *Оплата из любой точки мира* (шекели)
"""
    
    await query.message.reply_text(
        back_text,
        reply_markup=keyboard.get_payment_method_keyboard(),
        parse_mode='Markdown'
    )

async def send_course_day1(query, context, payment_id, payment_method):
    """Отправляет первый день курса"""
    # Обновляем статус платежа
    user_id = db.update_payment_status(payment_id, "success")
    
    if user_id:
        # Отправляем уведомление администратору
        payment_data = {
            'user_id': user_id,
            'payment_id': payment_id,
            'amount': 599.00 if payment_method == "yookassa" else 30.00,
            'currency': "RUB" if payment_method == "yookassa" else "ILS",
            'payment_method': payment_method
        }
        payment_processor.notify_admin(payment_data)
        
        # Сообщение об успешной оплате
        success_text = """
✅ *Оплата прошла успешно!*

Доступ к курсу «Путь к мечте» активирован.

Первое задание уже ждет вас!
        """
        await query.edit_message_text(
            text=success_text,
            parse_mode='Markdown'
        )
        
        # День 1 - Разбуди своего Мечтателя
        await query.message.reply_text("""
👋 Здравствуйте! Сегодня — День 1 нашего путешествия: **Разбуди своего Мечтателя!**

Внутри каждого из нас живет **Внутренний Ребенок**. Именно эта часть личности умеет мечтать по-настоящему. 👶

Чем свободнее Внутренний Ребенок, тем легче нам мечтать и наполнять желания **энергией** для их реализации.
        """, parse_mode='Markdown')
        
        
        await query.message.reply_text("""
✨ Задание Дня: **Создаем Базовый Список Желаний**
Приготовьте **ручку и лист бумаги**. 📝

Сядьте удобно, расслабьтесь. Представьте своего **Внутреннего Мечтателя**, погрузитесь в это состояние.

Начинайте записывать **всё, что вспомните**. НЕ включайте логику и здравый смысл! Вспомните желания из прошлого, а затем добавьте те, что актуальны сейчас.

Примеры того, что записываем:
• 💖 Желания, связанные с любовью, теплом и заботой.
• 🤸‍♀️ Потребности (отдых, еда, активность).
• 🏆 Цели, достижения и материальные желания.
• 🌍 Новые впечатления и познание мира.
        """, parse_mode='Markdown')
        
        
        await query.message.reply_text("""
✍️ **Напоминание:**

Список можно дополнять, пока вы не получите следующее письмо от меня!

Обязательно **СОХРАНИТЕ ЭТОТ СПИСОК!** Он понадобится вам для выполнения всех последующих заданий курса.

⏰ До встречи завтра в это же время!
        """, parse_mode='Markdown')
        
        # Отмечаем в БД, что пользователь активировал курс
        # (нужно добавить поле is_premium в таблицу users)
    else:
        await query.answer(
            text="❌ Платеж не найден или не подтвержден",
            show_alert=True
        )


# Глобальный словарь для хранения задач отправки
user_tasks = {}

# Контент курса (можно вынести в БД или отдельный файл)
COURSE_CONTENT = {
    1: [
        "👋 Здравствуйте! Сегодня — День 1 нашего путешествия: **Разбуди своего Мечтателя!**",
        "Внутри каждого из нас живет **Внутренний Ребенок**. Именно эта часть личности умеет мечтать по-настоящему. 👶",
        "Чем свободнее Внутренний Ребенок, тем легче нам мечтать и наполнять желания **энергией** для их реализации.",
        "",
        "✨ **Задание Дня 1: Создаем Базовый Список Желаний**",
        "Приготовьте **ручку и лист бумаги**. 📝",
        "Сядьте удобно, расслабьтесь. Представьте своего **Внутреннего Мечтателя**...",
        # ... остальной текст дня 1
    ],
    2: [
        "🎉 **День 2: Уточняем и структурируем желания**",
        "Сегодня мы будем работать со списком, который вы создали вчера.",
        "Выделите 3 самых важных желания из вашего списка...",
        # ... текст дня 2
    ],
    # ... дни 3-7
}

async def schedule_course_messages(user_id: int, application):
    """Планирует отправку 7-дневного курса"""
    try:
        # Проверяем, не запущен ли уже курс для этого пользователя
        if user_id in user_tasks:
            logging.info(f"⚠️ Course already scheduled for user {user_id}")
            return
        
        # Создаем задачу для пользователя
        task = asyncio.create_task(send_course_for_user(user_id, application))
        user_tasks[user_id] = task
        
        logging.info(f"✅ Scheduled 7-day course for user {user_id}")
        
    except Exception as e:
        logging.error(f"❌ Error scheduling course for user {user_id}: {e}")

async def send_course_for_user(user_id: int, application, start_day: int = 1):
    """Отправляет курс пользователю в течение 7 дней"""
    try:
        for day in range(start_day, 8):
            # Отправляем сообщения дня
            await send_day_messages(user_id, day, application)
            
            # Ждем 24 часа перед следующим днем (кроме последнего)
            if day < 7:
                await asyncio.sleep(24 * 60 * 60)  # 24 часа в секундах
                
        # Курс завершен
        await send_course_completion(user_id, application)
        
        # Очищаем задачу
        if user_id in user_tasks:
            del user_tasks[user_id]
            
        # Отмечаем в БД как завершенный
        mark_course_completed(user_id)
        
    except asyncio.CancelledError:
        logging.info(f"Course cancelled for user {user_id}")
    except Exception as e:
        logging.error(f"❌ Error sending course to user {user_id}: {e}")
        # Очищаем задачу при ошибке
        if user_id in user_tasks:
            del user_tasks[user_id]

async def send_day_messages(user_id: int, day: int, application):
    """Отправляет все сообщения для определенного дня"""
    messages = COURSE_CONTENT.get(day, [])
    
    if not messages:
        logging.error(f"No content for day {day}")
        return
    
    try:
        # Отправляем первое сообщение с заголовком дня
        await application.bot.send_message(
            chat_id=user_id,
            text=f"📅 **День {day}/7**\n\n{messages[0]}",
            parse_mode='Markdown'
        )
        
        # Отправляем остальные сообщения с задержкой
        for i, message in enumerate(messages[1:], 1):
            if message.strip():  # Пропускаем пустые строки
                await asyncio.sleep(1)  # 1 секунда между сообщениями
                await application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown' if i < len(messages)-1 else None
                )
        
        # Обновляем прогресс в БД
        update_user_progress(user_id, day)
        
        logging.info(f"✅ Sent day {day} to user {user_id}")
        
    except Exception as e:
        logging.error(f"❌ Error sending day {day} to user {user_id}: {e}")

async def send_course_completion(user_id: int, application):
    """Отправляет сообщение о завершении курса"""
    completion_text = """
🎉 **Поздравляем! Вы завершили 7-дневный курс "Путь к мечте"!**

Вы проделали огромную работу над собой:
✅ Разбудили своего Внутреннего Мечтателя
✅ Сформулировали четкие цели
✅ Создали план действий

Теперь у вас есть все инструменты для реализации ваших желаний!

Если вам понравился курс, поделитесь впечатлениями с друзьями ❤️

С любовью,
Светлана Скромова
    """
    
    try:
        await application.bot.send_message(
            chat_id=user_id,
            text=completion_text,
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"Error sending completion to {user_id}: {e}")

def update_user_progress(user_id: int, current_day: int):
    """Обновляет прогресс пользователя в БД"""
    conn = db.get_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        
        # Проверяем, существует ли запись
        cursor.execute(
            "SELECT id FROM course_progress WHERE user_id = %s",
            (user_id,)
        )
        
        if cursor.fetchone():
            # Обновляем существующую запись
            cursor.execute('''
                UPDATE course_progress 
                SET current_day = %s, 
                    last_message_date = NOW(),
                    is_active = CASE WHEN %s >= 7 THEN FALSE ELSE TRUE END
                WHERE user_id = %s
            ''', (current_day, current_day, user_id))
        else:
            # Создаем новую запись
            cursor.execute('''
                INSERT INTO course_progress 
                (user_id, current_day, last_message_date, is_active)
                VALUES (%s, %s, NOW(), TRUE)
            ''', (user_id, current_day))
        
        conn.commit()
        
    except Exception as e:
        logging.error(f"❌ Error updating progress: {e}")
        conn.rollback()
    finally:
        conn.close()

def mark_course_completed(user_id: int):
    """Отмечает курс как завершенный"""
    conn = db.get_connection()
    if not conn:
        return
    
    try:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE course_progress 
            SET is_active = FALSE,
                completed_at = NOW()
            WHERE user_id = %s
        ''', (user_id,))
        conn.commit()
    except Exception as e:
        logging.error(f"Error marking course completed: {e}")
    finally:
        conn.close()

def get_user_current_day(user_id: int) -> int:
    """Получает текущий день курса для пользователя"""
    conn = db.get_connection()
    if not conn:
        return 1
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT current_day FROM course_progress WHERE user_id = %s",
            (user_id,)
        )
        result = cursor.fetchone()
        return result[0] if result else 1
    except Exception as e:
        logging.error(f"Error getting current day: {e}")
        return 1
    finally:
        conn.close()
