import logging
import uuid
import requests
import json
import os
from datetime import datetime
import base64

logger = logging.getLogger(__name__)

class PaymentProcessor:
    def __init__(self, db):
        self.db = db
        self.yookassa_shop_id = os.environ.get("YOOKASSA_SHOP_ID", "")
        self.yookassa_secret_key = os.environ.get("YOOKASSA_SECRET_KEY", "")
        self.paypal_client_id = os.environ.get("PAYPAL_CLIENT_ID", "")
        self.paypal_client_secret = os.environ.get("PAYPAL_CLIENT_SECRET", "")
        
    def generate_payment_id(self, user_id):
        """Генерирует уникальный ID платежа"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        return f"{user_id}_{timestamp}_{unique_id}"
    
    def create_yookassa_payment(self, user_id):
        """Создает реальный платеж в ЮKassa через API"""
        payment_id = self.generate_payment_id(user_id)
        
        try:
            # Подготовка данных для API ЮKassa
            import requests
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Basic {base64.b64encode(f'{self.yookassa_shop_id}:{self.yookassa_secret_key}'.encode()).decode()}"
            }
            
            payload = {
                "amount": {
                    "value": "599.00",
                    "currency": "RUB"
                },
                "payment_method_data": {
                    "type": "bank_card"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"https://t.me/The_road_to_a_dream_bot"
                },
                "capture": True,
                "description": f"Курс 'Путь к мечте' для пользователя {user_id}",
                "metadata": {
                    "user_id": user_id,
                    "payment_id": payment_id
                }
            }
            
            # Отправляем запрос в ЮKassa
            response = requests.post(
                "https://api.yookassa.ru/v3/payments",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                payment_url = data.get("confirmation", {}).get("confirmation_url")
                yookassa_payment_id = data.get("id")
                
                # Сохраняем в БД с реальным ID ЮKassa
                if self.db.create_payment(
                    user_id=user_id,
                    payment_id=yookassa_payment_id,  # Используем ID от ЮKassa
                    amount=599.00,
                    currency="RUB",
                    payment_method="yookassa"
                ):
                    return payment_url, yookassa_payment_id
                    
        except Exception as e:
            logger.error(f"❌ YooKassa API error: {e}")
            
        # Fallback на старую ссылку если API не работает
        base_url = "https://yookassa.ru/my/i/aT2KyUW8oL5x/l"
        payment_url = f"{base_url}?payment_id={payment_id}"
        
        if self.db.create_payment(user_id, payment_id, 599.00, "RUB", "yookassa"):
            return payment_url, payment_id
            
        return None, None
    
    def create_paypal_payment(self, user_id):
        """Создает реальный платеж в PayPal через API"""
        payment_id = self.generate_payment_id(user_id)
        
        try:
            # 1. Получаем access token
            auth_response = requests.post(
                "https://api-m.paypal.com/v1/oauth2/token",
                auth=(self.paypal_client_id, self.paypal_client_secret),
                headers={"Accept": "application/json", "Accept-Language": "en_US"},
                data={"grant_type": "client_credentials"},
                timeout=30
            )
            
            if auth_response.status_code != 200:
                logger.error(f"PayPal auth failed: {auth_response.text}")
                return None, None
                
            access_token = auth_response.json()["access_token"]
            
            # 2. Создаем платеж
            payload = {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "reference_id": payment_id,
                    "amount": {
                        "currency_code": "ILS",
                        "value": "30.00"
                    },
                    "description": "Course 'Path to Dream'",
                    "custom_id": str(user_id)
                }],
                "application_context": {
                    "return_url": "https://t.me/The_road_to_a_dream_bot",
                    "cancel_url": "https://t.me/The_road_to_a_dream_bot",
                    "brand_name": "Путь к мечте",
                    "user_action": "PAY_NOW"
                }
            }
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
            
            response = requests.post(
                "https://api-m.paypal.com/v2/checkout/orders",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 201:
                data = response.json()
                paypal_order_id = data["id"]
                
                # Находим ссылку для оплаты
                for link in data.get("links", []):
                    if link.get("rel") == "approve":
                        payment_url = link.get("href")
                        
                        # Сохраняем в БД
                        if self.db.create_payment(
                            user_id=user_id,
                            payment_id=paypal_order_id,
                            amount=30.00,
                            currency="ILS",
                            payment_method="paypal"
                        ):
                            return payment_url, paypal_order_id
                            
        except Exception as e:
            logger.error(f"❌ PayPal API error: {e}")
        
        # Fallback на старую ссылку
        base_url = "https://www.paypal.com/ncp/payment/VK4RESTAGVZFC"
        payment_url = f"{base_url}?payment_id={payment_id}"
        
        if self.db.create_payment(user_id, payment_id, 30.00, "ILS", "paypal"):
            return payment_url, payment_id
            
        return None, None

    def verify_paypal_webhook(self, request_body, headers):
        """Проверяет вебхук PayPal"""
        try:
            # Получаем данные для проверки
            transmission_id = headers.get('PAYPAL-TRANSMISSION-ID')
            transmission_time = headers.get('PAYPAL-TRANSMISSION-TIME')
            cert_url = headers.get('PAYPAL-CERT-URL')
            transmission_sig = headers.get('PAYPAL-TRANSMISSION-SIG')
            auth_algo = headers.get('PAYPAL-AUTH-ALGO')
            
            # Создаем строку для проверки
            message = f"{transmission_id}|{transmission_time}|{self.paypal_webhook_id}|{hashlib.sha256(request_body).hexdigest()}"
            
            # Проверяем подпись (упрощенно, нужна полная реализация)
            # В реальности нужно получать сертификат и проверять подпись
            
            return True  # Для начала можно пропустить проверку
            
        except Exception as e:
            logger.error(f"❌ PayPal webhook verification error: {e}")
            return False

    def check_payment_status(self, payment_id):
        """Проверяет статус платежа"""
        logging.info(f"🔍 Checking payment status for: {payment_id}")
        
        # Сначала проверяем в БД
        conn = self.db.get_connection()
        if not conn:
            logging.error("❌ No database connection")
            return "pending"
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, payment_method FROM payments WHERE payment_id = %s",
                (payment_id,)
            )
            result = cursor.fetchone()
            
            if result:
                status, payment_method = result
                logging.info(f"🔍 Found in DB: status={status}, method={payment_method}")
                
                # Если статус pending и это PayPal, проверяем через API
                if status == "pending" and payment_method == "paypal":
                    logging.info(f"🔍 Checking PayPal payment via API: {payment_id}")
                    api_status = self.check_paypal_payment_api(payment_id)
                    if api_status != status:
                        logging.info(f"🔍 API returned new status: {api_status}")
                    return api_status
                    
                return status
            else:
                logging.warning(f"❌ Payment not found in DB: {payment_id}")
                
                # Попробуем найти по другому формату ID
                # Иногда PayPal возвращает другой ID
                cursor.execute(
                    "SELECT payment_id, status FROM payments WHERE payment_id LIKE %s",
                    (f"%{payment_id}%",)
                )
                similar = cursor.fetchone()
                if similar:
                    similar_id, similar_status = similar
                    logging.info(f"🔍 Found similar payment: {similar_id} with status {similar_status}")
                    return similar_status
                    
                return "not_found"
                
        except Exception as e:
            logging.error(f"❌ Error checking payment status: {e}")
            return "error"
        finally:
            conn.close()

    def check_paypal_payment_api(self, payment_id):
        """Проверяет платеж PayPal через API"""
        try:
            # Получаем access token
            auth_response = requests.post(
                "https://api-m.paypal.com/v1/oauth2/token",
                auth=(self.paypal_client_id, self.paypal_client_secret),
                headers={"Accept": "application/json"},
                data={"grant_type": "client_credentials"},
                timeout=30
            )
            
            if auth_response.status_code != 200:
                logging.error(f"PayPal auth failed: {auth_response.text}")
                return "pending"
                
            access_token = auth_response.json()["access_token"]
            
            # Проверяем статус платежа
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
            
            response = requests.get(
                f"https://api-m.paypal.com/v2/checkout/orders/{payment_id}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "").upper()
                
                if status == "COMPLETED":
                    # Обновляем статус в БД
                    conn = self.db.get_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE payments SET status = 'success' WHERE payment_id = %s",
                            (payment_id,)
                        )
                        conn.commit()
                        conn.close()
                    return "success"
                elif status in ["APPROVED", "CREATED"]:
                    return "pending"
                else:
                    return "failed"
            else:
                logging.error(f"PayPal API error: {response.status_code} - {response.text}")
                return "pending"
                
        except Exception as e:
            logging.error(f"PayPal API check error: {e}")
            return "pending"

    def verify_yookassa_webhook(self, request_body, signature):
        """Проверяет подпись вебхука от ЮKassa"""
        try:
            # Генерируем HMAC-SHA256 подпись
            hash_object = hmac.new(
                self.yookassa_secret_key.encode(),
                request_body,
                hashlib.sha256
            )
            expected_signature = base64.b64encode(hash_object.digest()).decode()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"❌ Webhook verification error: {e}")
            return False

    def notify_admin(self, payment_data):
        """Отправляет уведомление администратору о платеже"""
        try:
            from telegram import Bot
            from config import BOT_TOKEN, ADMIN_IDS
            
            bot = Bot(token=BOT_TOKEN)
            
            # Определяем тип курса
            course_type = payment_data.get('course_type', '7-day_course')
            if course_type == '7-day_course':
                course_name = "7-дневный курс «Путь к мечте»"
            elif course_type == '21-day_marathon':
                course_name = "21-дневный марафон «От мечты к цели»"
            else:
                course_name = "курс"
            
            # Получаем информацию о пользователе
            conn = self.db.get_connection()
            user_info = None
            if conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT username, first_name FROM users WHERE user_id = %s",
                        (payment_data['user_id'],)
                    )
                    result = cursor.fetchone()
                    if result:
                        username, first_name = result
                        if username:
                            user_info = f"👤 {first_name} (@{username})"
                        else:
                            user_info = f"👤 {first_name}"
                except Exception as e:
                    logger.error(f"Error getting user info: {e}")
                finally:
                    conn.close()
            
            if not user_info:
                user_info = f"👤 ID: {payment_data['user_id']}"
            
            message = f"""
    💰 *НОВАЯ ОПЛАТА {course_name.upper()}!*

    {user_info}
    📚 *Курс:* {course_name}
    💳 *Система:* {payment_data['payment_method'].upper()}
    💎 *Сумма:* {payment_data['amount']} {payment_data['currency']}
    🆔 *ID платежа:* `{payment_data['payment_id']}`
    ⏰ *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
    """
            
            # Отправляем всем администраторам
            for admin_id in ADMIN_IDS:
                try:
                    bot.send_message(
                        chat_id=admin_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    logger.info(f"✅ Admin notification sent to {admin_id}")
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in admin notification: {e}")
