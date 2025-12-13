import os

# Токен бота из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in environment variables!")
# ID администратора
ADMIN_IDS = [int(id.strip()) for id in os.environ.get("ADMIN_IDS", "").split(",") if id.strip()]



# Настройки ЮKassa
YOOKASSA_SHOP_ID = os.environ.get("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.environ.get("YOOKASSA_SECRET_KEY", "")

# PayPal настройки
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_WEBHOOK_ID = os.environ.get("PAYPAL_WEBHOOK_ID", "")

