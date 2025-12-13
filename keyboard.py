from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_payment_method_keyboard():
    """Клавиатура для выбора платежной системы"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Оплата из России", callback_data="payment_yookassa")],
        [InlineKeyboardButton("🌍 Оплата из любой точки мира", callback_data="payment_paypal")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_yookassa_payment_keyboard(payment_url, payment_id):
    """Клавиатура после создания платежа ЮKassa - сразу с ссылкой"""
    keyboard = [
        [InlineKeyboardButton("💳 Перейти к оплате 599₽", url=payment_url)],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_yookassa_{payment_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="payment_yookassa")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_paypal_payment_keyboard(payment_url, payment_id):
    """Клавиатура после создания платежа PayPal - сразу с ссылкой"""
    keyboard = [
        [InlineKeyboardButton("💳 Перейти к оплате 30₪", url=payment_url)],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_paypal_{payment_id}")],
        [InlineKeyboardButton("◀️ Назад", callback_data="payment_paypal")]
    ]
    return InlineKeyboardMarkup(keyboard)