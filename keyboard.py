from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_payment_method_keyboard():
    """Клавиатура для выбора платежной системы"""
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Оплата из России", callback_data="payment_yookassa")],
        [InlineKeyboardButton("🌍 Оплата из любой точки мира", callback_data="payment_paypal")],
        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)