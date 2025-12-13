from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_payment_method_keyboard():
    """Клавиатура для выбора платежной системы"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Оплата из России", callback_data="payment_yookassa")],
        [InlineKeyboardButton("🌍 Оплата из любой точки мира", callback_data="payment_paypal")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_yookassa_payment_keyboard():
    """Клавиатура для оплаты через ЮKassa"""
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить 599₽", url=payment_url)],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data="check_yookassa_payment")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_paypal_payment_keyboard():
    """Клавиатура для оплаты через PayPal"""
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить 30₪", url=payment_url)],
        [InlineKeyboardButton("🔄 Проверить оплату", callback_data="check_paypal_payment")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_yookassa_initial_keyboard():
    """Первая клавиатура для ЮKassa - сразу оплата"""
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить 599₽", callback_data="process_yookassa_payment")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_payment_method")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_paypal_initial_keyboard():
    """Первая клавиатура для PayPal - сразу оплата"""
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить 30₪", callback_data="process_paypal_payment")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_payment_method")]
    ]
    return InlineKeyboardMarkup(keyboard)
