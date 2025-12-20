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


logger = logging.getLogger(__name__)
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
        await create_yookassa_payment(query, context)  
    
    elif query.data == "payment_paypal":
        await create_paypal_payment(query, context) 
    
    elif query.data.startswith("check_yookassa_"):
        await check_specific_payment(query, context, "yookassa")
    
    elif query.data.startswith("check_paypal_"):
        await check_specific_payment(query, context, "paypal")
    
    elif query.data == "back_to_payment_method":
        await back_to_payment_methods(query, context)

    elif query.data == "payment_yookassa_retry":
        await query.message.reply_text("🔄 Создаю новый платеж...")
        await create_yookassa_payment(query, context)
    
    elif query.data == "payment_paypal_retry":
        await query.message.reply_text("🔄 Создаю новый платеж...")
        await create_paypal_payment(query, context)

    elif query.data == "marathon_info":
        await show_marathon_info(query, context)
    
    elif query.data == "marathon_payment":
        await show_marathon_payment_methods(query, context)
    
    elif query.data == "marathon_yookassa":
        await create_marathon_yookassa_payment(query, context)
    
    elif query.data == "marathon_paypal":
        await create_marathon_paypal_payment(query, context)
    
    elif query.data.startswith("check_marathon_yookassa_"):
        await check_marathon_payment(query, context, "yookassa")
    
    elif query.data.startswith("check_marathon_paypal_"):
        await check_marathon_payment(query, context, "paypal")

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

async def create_yookassa_payment(query, context: ContextTypes.DEFAULT_TYPE):
    """Создает платеж ЮKassa и сразу показывает ссылку"""
    user_id = query.from_user.id
    
    # Создаем платеж
    payment_url, payment_id = payment_processor.create_yookassa_payment(user_id)
    
    if payment_url:
        # Сохраняем payment_id для проверки
        context.user_data['last_payment_id'] = payment_id
        
        payment_text = f"""
💳 *Оплата из России*
✅ *Стоимость:* 599 рублей

Нажмите кнопку ниже для перехода к оплате.

После успешной оплаты доступ к курсу откроется автоматически в течение 1-2 минут.
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
    """Создает платеж PayPal и сразу показывает ссылку"""
    user_id = query.from_user.id
    
    # Создаем платеж
    payment_url, payment_id = payment_processor.create_paypal_payment(user_id)
    
    if payment_url:
        # Сохраняем payment_id для проверки
        context.user_data['last_payment_id'] = payment_id
        
        payment_text = f"""
💳 *Оплата из любой точки мира*
✅ *Стоимость:* 30 шекелей 

Нажмите кнопку ниже для перехода к оплате.

После успешной оплаты доступ к курсу откроется автоматически в течение 1-2 минут.

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
    logging.info(f"🔍 Starting check_specific_payment: {method}")
    
    # Извлекаем payment_id из callback_data
    payment_id = query.data.replace(f"check_{method}_", "")
    logging.info(f"🔍 Payment ID to check: {payment_id}")
    
    try:
        # Сначала отвечаем на callback
        await query.answer()
        
        # Проверяем статус платежа
        logging.info(f"🔍 Calling check_payment_status for {payment_id}")
        status = payment_processor.check_payment_status(payment_id)
        logging.info(f"🔍 Payment status: {status}")
        
        if status == "success":
            logging.info(f"✅ Payment successful! Activating course for user {query.from_user.id}")
            
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
                logging.info(f"✅ Message deleted for payment {payment_id}")
            except Exception as e:
                logging.error(f"❌ Error deleting message: {e}")
                
        elif status == "pending":
            logging.info(f"⏳ Payment still pending for {payment_id}")
            
            # Отправляем сообщение пользователю с кнопкой проверки
            pending_text = f"""
⏳ *Платеж обрабатывается*

Платеж `{payment_id}` еще обрабатывается платежной системой.

⏱️ *Обычное время обработки:* 1-5 минут

💡 *Рекомендации:*
1. Подождите 2-3 минуты
2. Нажмите кнопку «Проверить снова» ниже
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить снова", callback_data=f"check_{method}_{payment_id}")],
                [InlineKeyboardButton("💳 Создать новый платеж", callback_data=f"payment_{method}")],
                [InlineKeyboardButton("◀️ Выбрать другой способ", callback_data="back_to_payment_method")]
            ])
            
            await query.message.reply_text(
                pending_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif status == "not_found":
            logging.warning(f"❌ Payment not found: {payment_id}")
            
            not_found_text = f"""
❌ *Платеж не найден*

Платеж `{payment_id}` не найден в системе.

⚠️ *Возможные причины:*
• Платеж еще не создан
• Произошла ошибка при создании
• ID платежа изменился

🔄 *Создайте новый платеж:*
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Создать новый платеж", callback_data=f"payment_{method}")],
                [InlineKeyboardButton("◀️ Вернуться к выбору", callback_data="back_to_payment_method")]
            ])
            
            await query.message.reply_text(
                not_found_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        elif status == "failed" or status == "canceled":
            logging.warning(f"❌ Payment failed/canceled: {payment_id}")
            
            failed_text = f"""
❌ *Платеж не прошел*

Платеж `{payment_id}` был отменен или не прошел.

⚠️ *Возможные причины:*
• Недостаточно средств на карте
• Карта отклонена банком
• Вы отменили платеж
• Истекло время оплаты

🔄 *Создайте новый платеж:*
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Создать новый платеж", callback_data=f"payment_{method}")],
                [InlineKeyboardButton("◀️ Вернуться к выбору", callback_data="back_to_payment_method")]
            ])
            
            await query.message.reply_text(
                failed_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
        else:  # error или другой статус
            logging.error(f"❌ Unknown payment status: {status} for {payment_id}")
            
            error_text = f"""
⚠️ *Ошибка проверки платежа*

Не удалось проверить статус платежа `{payment_id}`.

⏰ *Статус:* `{status}`
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Проверить снова", callback_data=f"check_{method}_{payment_id}")],
                [InlineKeyboardButton("💳 Создать новый платеж", callback_data=f"payment_{method}")]
            ])
            
            await query.message.reply_text(
                error_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logging.error(f"❌ Error in check_specific_payment: {e}", exc_info=True)
        
        error_text = f"""
🚨 *Произошла ошибка*

При проверке платежа произошла ошибка.

        """
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Создать новый платеж", callback_data=f"payment_{method}")],
            [InlineKeyboardButton("◀️ Вернуться к выбору", callback_data="back_to_payment_method")]
        ])
        
        await query.message.reply_text(
            error_text,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

async def activate_course_after_payment(user_id: int, payment_id: str, method: str, application):
    """Активирует курс после успешной оплаты"""
    logging.info(f"🚀 START activate_course_after_payment for user {user_id}")
    
    try:
        # Создаем запись о покупке курса
        logging.info(f"📝 Creating course progress for user {user_id}")
        conn = db.get_connection()
        if conn:
            cursor = conn.cursor()
            
            # Удаляем старую запись если есть
            cursor.execute("DELETE FROM course_progress WHERE user_id = %s", (user_id,))
            
            # Создаем новую запись
            cursor.execute('''
                INSERT INTO course_progress 
                (user_id, current_day, last_message_date, is_active)
                VALUES (%s, 1, NOW(), TRUE)
            ''', (user_id,))
            
            conn.commit()
            conn.close()
            logging.info(f"✅ Course progress created for user {user_id}")
        else:
            logging.error("❌ No database connection")
        
        # Отправляем сообщение об успешной оплате
        logging.info(f"📨 Sending success message to user {user_id}")
        await application.bot.send_message(
            chat_id=user_id,
            text="""✅ *Оплата прошла успешно!*

🎉 Доступ к курсу «Путь к мечте» активирован!

Первое задание уже ждет вас ниже ⬇️""",
            parse_mode='Markdown'
        )
        
        # Сразу отправляем День 1
        logging.info(f"📚 Sending Day 1 to user {user_id}")
        await send_course_day1(user_id, application)
        
        # Уведомляем администратора
        logging.info(f"📢 Notifying admin about user {user_id}")
        payment_processor.notify_admin({
            'user_id': user_id,
            'payment_id': payment_id,
            'amount': 599.00 if method == "yookassa" else 30.00,
            'currency': "RUB" if method == "yookassa" else "ILS",
            'payment_method': method,
            'course_type': "7-day_course"
        })
        
        logging.info(f"✅ Course fully activated for user {user_id}")
        
    except Exception as e:
        logging.error(f"❌ Error activating course for user {user_id}: {e}", exc_info=True)
        # Пытаемся отправить пользователю сообщение об ошибке
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text="❌ Произошла ошибка при активации курса. Мы уже работаем над решением. Попробуйте позже."
            )
        except:
            pass

async def send_fallback_day1(user_id: int, application):
    """Запасной вариант отправки дня 1 если БД не работает"""
    try:
        day1_messages = [
            "📅 **День 1/7**\n\nЗдравствуйте! Сегодня — День 1 нашего путешествия: **Разбуди своего Мечтателя!**",
            "Внутри каждого из нас живет **Внутренний Ребенок.** Именно эта часть личности умеет мечтать по-настоящему.",
            "Чем свободнее Внутренний Ребенок, тем легче нам мечтать и наполнять желания **энергией** для их реализации.",
            "",
            "Задание Дня: **Создаем Базовый Список Желаний**",
            "Приготовьте **ручку и лист бумаги.**",
            "",
            "Сядьте удобно, расслабьтесь. Представьте своего **Внутреннего Мечтателя,** погрузитесь в это состояние.",
            "",
            "Начинайте записывать **всё, что вспомните.** НЕ включайте логику и здравый смысл! Вспомните желания из прошлого, а затем добавьте те, что актуальны сейчас.",
            "",
            "Примеры того, что записываем:",
            "• Желания, связанные с любовью, теплом и заботой.",
            "• Потребности (отдых, еда, активность).",
            "• Цели, достижения и материальные желания.",
            "• Новые впечатления и познание мира.",
            "",
            "**Напоминание:**",
            "Список можно дополнять, пока вы не получите следующее письмо от меня!",
            "",
            "Обязательно **СОХРАНИТЕ ЭТОТ СПИСОК!** Он понадобится вам для выполнения всех последующих заданий курса.",
            "",
            "До встречи завтра в это же время!"
        ]
        
        for message in day1_messages:
            if message.strip():
                await application.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown' if "**" in message or "•" in message else None
                )
                await asyncio.sleep(0.5)
                
        logging.info(f"✅ Sent fallback Day 1 to user {user_id}")
        
    except Exception as e:
        logging.error(f"❌ Error in fallback Day 1: {e}")

async def back_to_payment_methods(query, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к выбору метода оплаты"""
    back_text = """
🔄 *Возвращаемся к выбору оплаты*

Выберите способ оплаты:

🇷🇺 *Оплата из России* (599 рублей)
🌍 *Оплата из любой точки мира* (30 шекелей)

"""
    
    await query.message.reply_text(
        back_text,
        reply_markup=keyboard.get_payment_method_keyboard(),
        parse_mode='Markdown'
    )

async def send_course_day1(user_id: int, application):
    """Отправляет первый день курса"""
    print(f"📖 START send_course_day1 for user {user_id}")
    
    try:
        content = db.get_course_content(1)
        
        if content:
            messages = content['messages']
            
            if isinstance(messages, list):
                for i, message in enumerate(messages):
                    if message and str(message).strip():
                        try:
                            # Конвертируем в HTML
                            html_message = db.markdown_to_html(str(message))
                            print(f"📨 HTML message: {html_message[:100]}...")
                            
                            await application.bot.send_message(
                                chat_id=user_id,
                                text=html_message,
                                parse_mode='HTML'
                            )
                            await asyncio.sleep(1)
                        except Exception as e:
                            print(f"Error: {e}")
                            await application.bot.send_message(
                                chat_id=user_id,
                                text=str(message),
                                parse_mode=None
                            )
            
            print(f"✅ Day 1 sent to user {user_id}")
        else:
            await send_fallback_day1(user_id, application)
        
    except Exception as e:
        print(f"Error: {e}")

async def send_fallback_day1(user_id: int, application):
    """Запасной вариант отправки дня 1"""
    try:
        day1_messages = [
            "👋 **Здравствуйте! Сегодня — День 1 нашего путешествия: Разбуди своего Мечтателя!**\n\n"
            "Внутри каждого из нас живет **Внутренний Ребенок.** Именно эта часть личности умеет мечтать по-настоящему. 👶\n\n"
            "Чем свободнее Внутренний Ребенок, тем легче нам мечтать и наполнять желания **энергией** для их реализации.",
            
            "✨ **Задание Дня: Создаем Базовый Список Желаний**\n"
            "Приготовьте **ручку и лист бумаги.** 📝\n\n"
            "Сядьте удобно, расслабьтесь. Представьте своего **Внутреннего Мечтателя,** погрузитесь в это состояние.\n\n"
            "Начинайте записывать **всё, что вспомните.** НЕ включайте логику и здравый смысл! Вспомните желания из прошлого, а затем добавьте те, что актуальны сейчас.\n\n"
            "**Примеры того, что записываем:**\n"
            "• 💖 Желания, связанные с любовью, теплом и заботой.\n"
            "• 🤸‍♀️ Потребности (отдых, еда, активность).\n"
            "• 🏆 Цели, достижения и материальные желания.\n"
            "• 🌍 Новые впечатления и познание мира.",
            
            "✍️ **Напоминание:**\n"
            "Список можно дополнять, пока вы не получите следующее письмо от меня!\n\n"
            "Обязательно **СОХРАНИТЕ ЭТОТ СПИСОК!** Он понадобится вам для выполнения всех последующих заданий курса.\n\n"
            "⏰ **До встречи завтра в это же время!**"
        ]
        
        for message in day1_messages:
            await application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown'  # ВСЕГДА Markdown
            )
            await asyncio.sleep(1)
            
        print(f"✅ Fallback Day 1 sent to user {user_id}")
        
    except Exception as e:
        print(f"❌ Error in fallback Day 1: {e}")

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

async def activate_course_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для ручной активации курса администратором"""
    user = update.effective_user
    
    # Проверяем права администратора
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Проверяем аргументы команды
    if not context.args:
        await update.message.reply_text(
            "📋 Использование: `/activate_course <user_id>`\n\n"
            "Пример: `/activate_course 123456789`",
            parse_mode='Markdown'
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        logging.info(f"🎯 Admin {user.id} activating course for user {target_user_id}")
        
        # Проверяем, существует ли пользователь
        conn = db.get_connection()
        if not conn:
            await update.message.reply_text("❌ Ошибка подключения к базе данных.")
            return
        
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (target_user_id,))
        user_exists = cursor.fetchone()
        conn.close()
        
        if not user_exists:
            await update.message.reply_text(f"❌ Пользователь с ID {target_user_id} не найден.")
            return
        
        # Создаем фиктивный платеж для отслеживания
        payment_id = f"manual_{datetime.now().strftime('%Y%m%d%H%M%S')}_{target_user_id}"
        
        # Сохраняем в БД как успешный платеж
        if db.create_payment(target_user_id, payment_id, 0.00, "MANUAL", "manual"):
            db.update_payment_status(payment_id, "success")
            
            # Активируем курс
            await activate_course_after_payment(
                target_user_id,
                payment_id,
                "manual",
                context.application
            )
            
            # Уведомляем администратора
            payment_processor.notify_admin({
                'user_id': target_user_id,
                'payment_id': payment_id,
                'amount': 0.00,
                'currency': "MANUAL",
                'payment_method': "manual_activation"
            })
            
            await update.message.reply_text(
                f"✅ Курс успешно активирован для пользователя {target_user_id}!\n"
                f"🆔 ID активации: `{payment_id}`",
                parse_mode='Markdown'
            )
            
        else:
            await update.message.reply_text("❌ Ошибка при создании записи об активации.")
            
    except ValueError:
        await update.message.reply_text("❌ Неверный формат ID пользователя. Используйте числа.")
    except Exception as e:
        logging.error(f"Error in activate_course_command: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику (только для администраторов)"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    try:
        conn = db.get_connection()
        if not conn:
            await update.message.reply_text("❌ Ошибка подключения к базе данных.")
            return
        
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM payments WHERE status = 'success'")
        successful_payments = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM course_progress WHERE is_active = TRUE")
        active_courses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM course_progress WHERE current_day >= 7")
        completed_courses = cursor.fetchone()[0]
        
        # Последние 5 платежей
        cursor.execute('''
            SELECT p.user_id, u.first_name, u.username, p.amount, p.currency, 
                   p.payment_method, p.created_at, p.status
            FROM payments p
            LEFT JOIN users u ON p.user_id = u.user_id
            ORDER BY p.created_at DESC
            LIMIT 5
        ''')
        recent_payments = cursor.fetchall()
        
        conn.close()
        
        # Формируем сообщение
        stats_text = f"""
📊 *СТАТИСТИКА БОТА*

👥 Всего пользователей: *{total_users}*
💰 Успешных оплат: *{successful_payments}*
📚 Активных курсов: *{active_courses}*
🎓 Завершенных курсов: *{completed_courses}*

💸 *Последние платежи:*
"""
        
        for payment in recent_payments:
            user_id, first_name, username, amount, currency, method, created_at, status = payment
            user_name = f"{first_name} (@{username})" if username else f"{first_name}"
            time_str = created_at.strftime('%d.%m %H:%M') if created_at else "N/A"
            
            status_emoji = "✅" if status == "success" else "⏳" if status == "pending" else "❌"
            
            stats_text += f"\n{status_emoji} {user_name} - {amount} {currency} ({method}) - {time_str}"
        
        stats_text += f"\n\n🆔 Ваш ID: `{user.id}`"
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in stats_command: {e}")
        await update.message.reply_text(f"❌ Ошибка получения статистики: {e}")

async def check_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет статус пользователя (для администраторов)"""
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    if not context.args:
        target_user_id = update.effective_user.id
    else:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("❌ Неверный формат ID пользователя.")
            return
    
    try:
        conn = db.get_connection()
        if not conn:
            await update.message.reply_text("❌ Ошибка подключения к базе данных.")
            return
        
        cursor = conn.cursor()
        
        # Информация о пользователе
        cursor.execute(
            "SELECT username, first_name, last_name, registered_date FROM users WHERE user_id = %s",
            (target_user_id,)
        )
        user_info = cursor.fetchone()
        
        # Платежи пользователя
        cursor.execute(
            "SELECT payment_id, amount, currency, payment_method, status, created_at FROM payments WHERE user_id = %s ORDER BY created_at DESC",
            (target_user_id,)
        )
        payments = cursor.fetchall()
        
        # Прогресс курса
        cursor.execute(
            "SELECT current_day, last_message_date, is_active FROM course_progress WHERE user_id = %s",
            (target_user_id,)
        )
        progress = cursor.fetchone()
        
        conn.close()
        
        # Формируем сообщение
        if user_info:
            username, first_name, last_name, registered_date = user_info
            user_display = f"{first_name} {last_name}" if first_name or last_name else "Без имени"
            if username:
                user_display += f" (@{username})"
            
            info_text = f"""
👤 *Информация о пользователе:*

🆔 ID: `{target_user_id}`
📛 Имя: {user_display}
📅 Регистрация: {registered_date.strftime('%d.%m.%Y %H:%M') if registered_date else 'N/A'}
"""
        else:
            info_text = f"👤 Пользователь с ID `{target_user_id}` не найден в базе данных.\n"
        
        # Информация о платежах
        if payments:
            info_text += f"\n💳 *Платежи ({len(payments)}):*\n"
            for payment in payments:
                payment_id, amount, currency, method, status, created_at = payment
                status_emoji = "✅" if status == "success" else "⏳" if status == "pending" else "❌"
                time_str = created_at.strftime('%d.%m %H:%M') if created_at else ""
                info_text += f"{status_emoji} {amount} {currency} ({method}) - {time_str}\n"
        else:
            info_text += "\n💳 *Платежи:* Нет\n"
        
        # Информация о прогрессе
        if progress:
            current_day, last_message_date, is_active = progress
            status = "🟢 Активен" if is_active else "🔴 Не активен"
            last_msg = f" ({last_message_date.strftime('%d.%m %H:%M')})" if last_message_date else ""
            info_text += f"\n📚 *Курс:* {status}\n"
            info_text += f"📅 Текущий день: {current_day}/7{last_msg}\n"
        else:
            info_text += "\n📚 *Курс:* Не активирован\n"
        
        await update.message.reply_text(info_text, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in check_user_command: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def show_marathon_info(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает информацию о марафоне"""
    marathon_info = """
🌟 **МАРАФОН «ОТ МЕЧТЫ К ЦЕЛИ»**

Вы прошли базовую подготовку на курсе, а Марафон поможет вам построить крепкое здание вашей мечты.

Это глубокий, 21-дневный процесс, направленный на **ВНЕДРЕНИЕ ЖЕЛАНИЙ В РЕАЛЬНУЮ ЖИЗНЬ.**

❓**ЧТО ВЫ ПОЛУЧИТЕ:**
💡 ЕЖЕДНЕВНЫЕ ЗАДАНИЯ в разнообразных форматах: текстовые практики, медитации, визуализация, работа с МАК и составление карты основных целей.
🧠 21 день вы будете находиться в **АКТИВНОМ СОПРИКОСНОВЕНИИ** со своими желаниями и мечтами, что позволит образоваться новым нейронным связям, которые помогут вам в итоге достичь желаемого.
💖 Вы **ОСОЗНАЕТЕ СВОИ ЦЕННОСТИ,** то, что является для вас приоритетным.
✅ Вы **СФОРМУЛИРУЕТЕ СВОИ ЖЕЛАНИЯ И ПОТРЕБНОСТИ,** опираясь на важные для вас ценности.
🗓️ Вы **ПРОПИШЕТЕ КОНКРЕТНЫЕ ЦЕЛИ** на ближайшие 12 месяцев.
🚀 Вы **СФОРМУЛИРУЕТЕ ШАГИ** для достижения целей.
💰 Вы **ОСОЗНАЕТЕ СВОИ РЕСУРСЫ,** которые помогут вам достичь желаемого.
🖼️ Вы **СОЗДАДИТЕ ЖЕЛАЕМУЮ КАРТИНКУ** своей жизни на ближайшее будущее.

🎯 Закрепление навыка **доведения целей до конца.**

🗓️ **СТАРТ: 4 ЯНВАРЯ 2026 ГОДА.**

🤝 **ФОРМАТ И ПОДДЕРЖКА**
⚡️Длительность: 21 день структурированной работы.
⚡️Площадка: Ежедневная работа и сопровождение в **ГРУППОВОМ ЧАТЕ TELEGRAM.**
⚡️Ценность сообщества: **ВЗАИМООБМЕН И ПЕРЕОПЫЛЕНИЕ** с другими участниками для **МОЩНОЙ ПОДДЕРЖКИ.**
⚡️Сопровождение: Личная поддержка и ответы на вопросы от дипломированного **ПСИХОТЕРАПЕВТА.**

🎁 **СПЕЦИАЛЬНАЯ СКИДКА 30%** действует для участников мини-курса! Не упустите возможность начать 2026 год с ясными целями и шагами для их реализации.
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Оплатить участие со скидкой 30%", callback_data="marathon_payment")],
        [InlineKeyboardButton("◀️ Назад", callback_data="go_back")]
    ])
    
    await query.message.reply_text(marathon_info, reply_markup=keyboard, parse_mode='Markdown')

async def show_marathon_payment_methods(query, context: ContextTypes.DEFAULT_TYPE):
    """Показывает методы оплаты марафона"""
    payment_text = """
💳 **Оплата участия в марафоне**

Выберите способ оплаты:

🇷🇺 **Оплата из России** - 4900 рублей
🌍 **Оплата из любой точки мира** - 245 шекелей

Обе системы обеспечивают безопасную оплату и мгновенную активацию подписки.
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇷🇺 Оплата из России (4900₽)", callback_data="marathon_yookassa")],
        [InlineKeyboardButton("🌍 Оплата из любой точки мира (245₪)", callback_data="marathon_paypal")],
        [InlineKeyboardButton("◀️ Назад", callback_data="marathon_info")]
    ])
    
    await query.message.reply_text(payment_text, reply_markup=keyboard, parse_mode='Markdown')

async def create_marathon_yookassa_payment(query, context: ContextTypes.DEFAULT_TYPE):
    """Создает платеж за марафон через ЮKassa"""
    user_id = query.from_user.id
    
    # Создаем специальный payment_id для марафона
    payment_id = f"marathon_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Используем существующую функцию с другими параметрами
    payment_url = "https://yookassa.ru/my/i/aUZE2BSiqy8l/l"
    
    if payment_url:
        # Сохраняем в БД как платеж за марафон
        if db.create_payment(user_id, payment_id, 4900.00, "RUB", "yookassa_marathon"):
            context.user_data['last_marathon_payment_id'] = payment_id
            
            payment_text = f"""
💳 *Оплата из России*
✅ *Стоимость:* 4900 рублей

Нажмите кнопку ниже для перехода к оплате марафона «От мечты к цели».

После успешной оплаты доступ к марафону будет активирован автоматически.

🆔 *ID платежа:* `{payment_id}`
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Перейти к оплате 4900₽", url=payment_url)],
                [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_marathon_yookassa_{payment_id}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="marathon_payment")]
            ])
            
            await query.message.reply_text(
                payment_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await query.answer("❌ Ошибка создания платежа", show_alert=True)

async def create_marathon_paypal_payment(query, context: ContextTypes.DEFAULT_TYPE):
    """Создает платеж за марафон через PayPal"""
    user_id = query.from_user.id
    
    # Создаем специальный payment_id для марафона
    payment_id = f"marathon_{user_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Здесь будет ссылка на PayPal для марафона
    payment_url = "ВАША_ССЫЛКА_PAYPAL_МАРАФОН"  # Замените на реальную ссылку
    
    if payment_url:
        # Сохраняем в БД как платеж за марафон
        if db.create_payment(user_id, payment_id, 245.00, "ILS", "paypal_marathon"):
            context.user_data['last_marathon_payment_id'] = payment_id
            
            payment_text = f"""
💳 *Оплата из любой точки мира*
✅ *Стоимость:* 245 шекелей (₪)

Нажмите кнопку ниже для перехода к оплате марафона «От мечты к цели».

После успешной оплаты доступ к марафону будет активирован автоматически.

🆔 *ID платежа:* `{payment_id}`
            """
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Перейти к оплате 245₪", url=payment_url)],
                [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_marathon_paypal_{payment_id}")],
                [InlineKeyboardButton("◀️ Назад", callback_data="marathon_payment")]
            ])
            
            await query.message.reply_text(
                payment_text,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )
        else:
            await query.answer("❌ Ошибка создания платежа", show_alert=True)

async def check_marathon_payment(query, context: ContextTypes.DEFAULT_TYPE, method: str):
    """Проверяет платеж за марафон"""
    payment_id = query.data.replace(f"check_marathon_{method}_", "")
    
    try:
        # Проверяем статус платежа
        status = payment_processor.check_payment_status(payment_id)
        
        if status == "success":
            # Активируем марафон
            await activate_marathon(query.from_user.id, payment_id, method, context.application)
            
            # Удаляем сообщение с кнопкой проверки
            try:
                await query.delete_message()
            except:
                pass
                
        elif status == "pending":
            await query.message.reply_text(
                "⏳ *Платеж за марафон обрабатывается*\n\n"
                "Подождите 2-3 минуты и нажмите «Проверить оплату» снова.",
                parse_mode='Markdown'
            )
        else:
            await query.message.reply_text(
                f"❌ *Платеж не прошел*\n\n"
                f"Статус: {status}\n\n"
                "Попробуйте создать новый платеж или выберите другой способ оплаты.",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logging.error(f"Error checking marathon payment: {e}")
        await query.message.reply_text(
            "❌ *Ошибка проверки платежа*\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            parse_mode='Markdown'
        )

async def activate_marathon(user_id: int, payment_id: str, method: str, application):
    """Активирует доступ к марафону"""
    try:
        # Отправляем подтверждение
        await application.bot.send_message(
            chat_id=user_id,
            text="""🎉 *Поздравляем с оплатой марафона «От мечты к цели»!*

✅ **Ваша оплата подтверждена!**

📅 **Старт марафона:** 4 января 2026 года

""",
            parse_mode='Markdown'
        )
        
        # Уведомляем администратора о платеже за марафон
        payment_processor.notify_admin({
            'user_id': user_id,
            'payment_id': payment_id,
            'amount': 4900.00 if method == "yookassa" else 245.00,
            'currency': "RUB" if method == "yookassa" else "ILS",
            'payment_method': method,
            'course_type': "21-day_marathon"
        })
        
        # Сохраняем информацию о покупке марафона
        conn = db.get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO marathon_purchases (user_id, payment_id, start_date)
                VALUES (%s, %s, %s)
            ''', (user_id, payment_id, "2026-01-04"))
            conn.commit()
            conn.close()
        
        logger.info(f"✅ Marathon activated for user {user_id}")
        
    except Exception as e:
        logging.error(f"❌ Error activating marathon: {e}")

async def reset_course_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для сброса и пересоздания контента курса (только для админов)"""
    user = update.effective_user
    
    from config import ADMIN_IDS
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для этой команды")
        return
    
    try:
        # Пересоздаем контент
        db.initialize_course_content()
        
        await update.message.reply_text(
            "✅ Контент курса успешно пересоздан!\n\n"
            "Структура:\n"
            "• День 1: 3 сообщения\n"
            "• День 2: 4 сообщения + 2 картинки\n"
            "• День 3: 3 сообщения\n"
            "• День 4: 3 сообщения\n"
            "• День 5: 3 сообщения\n"
            "• День 6: 3 сообщения\n"
            "• День 7: 3 сообщения",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error resetting course: {e}")
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def check_content_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверяет наличие контента курса"""
    user = update.effective_user
    
    from config import ADMIN_IDS
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Только для администраторов")
        return
    
    try:
        # Проверяем таблицу course_content
        conn = db.get_connection()
        if not conn:
            await update.message.reply_text("❌ Нет подключения к БД")
            return
        
        cursor = conn.cursor()
        
        # Получаем все дни
        cursor.execute("SELECT day_number, messages FROM course_content ORDER BY day_number")
        rows = cursor.fetchall()
        conn.close()
        
        days_info = []
        for row in rows:
            day_number, messages = row
            if isinstance(messages, str):
                try:
                    import json
                    messages_list = json.loads(messages)
                    message_count = len(messages_list) if isinstance(messages_list, list) else 1
                except:
                    message_count = 1
            elif isinstance(messages, list):
                message_count = len(messages)
            else:
                message_count = 1
            
            days_info.append(f"📅 День {day_number}: {message_count} сообщений")
        
        if days_info:
            status_text = "📊 Контент курса:\n\n" + "\n".join(days_info)
        else:
            status_text = "📭 В БД нет контента"
        
        await update.message.reply_text(status_text)
        
    except Exception as e:
        print(f"❌ Ошибка check_content: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def recreate_content_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пересоздает контент курса"""
    user = update.effective_user
    
    from config import ADMIN_IDS
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ Только для администраторов")
        return
    
    try:
        await update.message.reply_text("🔄 Пересоздаю контент курса...")
        
        # Очищаем старый контент
        conn = db.get_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM course_content")
            conn.commit()
            conn.close()
        
        # Создаем новый контент
        db.initialize_course_content()
        
        await update.message.reply_text(
            "✅ Контент курса успешно пересоздан!\n\n"
            "Используйте /check_content для проверки."
        )
        
    except Exception as e:
        error_msg = str(e).replace('*', '').replace('_', '').replace('`', "'")
        await update.message.reply_text(f"❌ Ошибка: {error_msg[:100]}")

async def test_simple_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Простая тестовая команда"""
    user = update.effective_user
    
    try:
        # Просто отправляем тестовое сообщение
        await update.message.reply_text(
            f"✅ Тест успешен!\n"
            f"🆔 Ваш ID: {user.id}\n"
            f"📛 Имя: {user.first_name}",
            parse_mode='Markdown'
        )
        
        # Проверяем БД
        conn = db.get_connection()
        if conn:
            await update.message.reply_text("✅ Подключение к БД: ОК")
            conn.close()
        else:
            await update.message.reply_text("❌ Нет подключения к БД")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:100]}")

async def debug_content_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отладочная команда для просмотра структуры контента"""
    user = update.effective_user
    
    from config import ADMIN_IDS
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("Нет доступа")
        return
    
    try:
        conn = db.get_connection()
        if not conn:
            await update.message.reply_text("❌ Нет БД")
            return
        
        cursor = conn.cursor()
        
        # Получаем структуру таблицы
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'course_content'
        """)
        columns = cursor.fetchall()
        
        # Получаем данные
        cursor.execute("SELECT * FROM course_content")
        rows = cursor.fetchall()
        
        conn.close()
        
        # Формируем сообщение
        result = "📊 Структура таблицы course_content:\n\n"
        
        for col_name, col_type in columns:
            result += f"• {col_name}: {col_type}\n"
        
        result += f"\n📈 Записей: {len(rows)}\n\n"
        
        for i, row in enumerate(rows):
            result += f"Запись {i+1}:\n"
            for j, col in enumerate(row):
                col_name = columns[j][0] if j < len(columns) else f"col_{j}"
                if col_name == 'messages':
                    if isinstance(col, str):
                        result += f"  {col_name}: строка ({len(col)} chars)\n"
                    elif isinstance(col, list):
                        result += f"  {col_name}: список ({len(col)} items)\n"
                    else:
                        result += f"  {col_name}: {type(col).__name__}\n"
                else:
                    result += f"  {col_name}: {col}\n"
            result += "\n"
        
        # Разбиваем на части если слишком длинное
        if len(result) > 4000:
            parts = [result[i:i+4000] for i in range(0, len(result), 4000)]
            for part in parts:
                await update.message.reply_text(part)
        else:
            await update.message.reply_text(result)
            
    except Exception as e:
        print(f"Debug error: {e}")
        await update.message.reply_text(f"Ошибка: {str(e)[:200]}")

async def test_markdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Тестирует Markdown разметку"""
    user = update.effective_user
    
    test_messages = [
        "Тест **жирного** текста",
        "Тест *курсива*",
        "Тест `моноширинного` текста",
        "Тест [ссылки](https://example.com)",
        "Тест **жирного с *курсивом***",
    ]
    
    for i, test_msg in enumerate(test_messages):
        try:
            # С Markdown
            await update.message.reply_text(
                f"Тест {i+1} (Markdown): {test_msg}",
                parse_mode='Markdown'
            )
            await asyncio.sleep(0.5)
            
            # Без Markdown
            await update.message.reply_text(
                f"Тест {i+1} (без разметки): {test_msg}",
                parse_mode=None
            )
            await asyncio.sleep(0.5)
            
        except Exception as e:
            await update.message.reply_text(f"Ошибка теста {i+1}: {e}")

