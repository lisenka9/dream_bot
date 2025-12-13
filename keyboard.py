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
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_yookassa_{payment_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_paypal_payment_keyboard(payment_url, payment_id):
    """Клавиатура после создания платежа PayPal - сразу с ссылкой"""
    keyboard = [
        [InlineKeyboardButton("💳 Перейти к оплате 30₪", url=payment_url)],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data=f"check_paypal_{payment_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_retry_keyboard(method: str):
    """Клавиатура для повторной оплаты"""
    if method == "yookassa":
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="payment_yookassa_retry")],
            [InlineKeyboardButton("◀️ Назад к выбору", callback_data="back_to_payment_method")]
        ]
    else: 
        keyboard = [
            [InlineKeyboardButton("🔄 Попробовать снова", callback_data="payment_paypal_retry")],
            [InlineKeyboardButton("◀️ Назад к выбору", callback_data="back_to_payment_method")]
        ]
    return InlineKeyboardMarkup(keyboard)