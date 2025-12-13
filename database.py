import os
import logging
from datetime import datetime, date, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor

class DatabaseManager:
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
    
    def get_connection(self):
        """Создает соединение с PostgreSQL с повторными попытками"""
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import time
        
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                conn = psycopg2.connect(
                    self.database_url,
                    sslmode='require',
                    connect_timeout=10,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5
                )
                return conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                if attempt < max_retries - 1:
                    logging.warning(f"⚠️ Database connection attempt {attempt + 1} failed: {e}")
                    logging.info(f"🔄 Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Экспоненциальная задержка
                else:
                    logging.error(f"❌ Failed to connect to database after {max_retries} attempts: {e}")
                    raise
            except Exception as e:
                logging.error(f"❌ Unexpected database connection error: {e}")
                raise
    
    def init_database(self):
        """Инициализация таблиц в базе данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            
            # Таблица пользователей - ИСПРАВЛЕНО
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    email TEXT,
                    registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    phone TEXT
                )
            ''')
        except Exception as e:
            logging.error(f"❌ Error initializing database: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_or_create_user(self, user_id: int, username: str, 
                          first_name: str, last_name: str) -> bool:
        """Создает или получает пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            username = username or ""
            first_name = first_name or "Пользователь"
            last_name = last_name or ""
            
            cursor.execute('''
                INSERT INTO users (user_id, username, first_name, last_name, registered_date)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO NOTHING
            ''', (user_id, username, first_name, last_name))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"❌ Error creating user: {e}")
            return False
        finally:
            conn.close()

    def create_course_purchase(self, user_id, payment_method='paypal'):
        """Создает запись о покупке курса"""
        conn = self.get_connection()
        if conn is None:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute(
                '''
                INSERT INTO course_purchases (user_id, payment_method)
                VALUES (%s, %s)
                ''',
                (user_id, payment_method)
            )
            
            # Создаем запись о прогрессе
            cursor.execute(
                '''
                INSERT INTO course_progress (user_id, current_day, last_message_date)
                VALUES (%s, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE
                SET is_active = TRUE,
                    current_day = 1,
                    last_message_date = CURRENT_TIMESTAMP
                ''',
                (user_id,)
            )
            
            conn.commit()
            logging.info(f"✅ Course purchase created for user {user_id}")
            return True
        except Exception as e:
            logging.error(f"❌ Error creating course purchase: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_users_for_daily_messages(self):
        """Возвращает пользователей, которым нужно отправить сообщения"""
        conn = self.get_connection()
        if conn is None:
            return []
        
        cursor = conn.cursor()
        try:
            # Находим пользователей, у которых:
            # 1. Курс активен (is_active = TRUE)
            # 2. Прошло более 24 часов с последнего сообщения
            # 3. Текущий день <= 7 (если 7+ дней - курс завершен)
            cursor.execute('''
                SELECT cp.user_id, cp.current_day
                FROM course_progress cp
                WHERE cp.is_active = TRUE
                  AND cp.current_day <= 7
                  AND (
                    cp.last_message_date IS NULL
                    OR cp.last_message_date < NOW() - INTERVAL '24 hours'
                  )
            ''')
            
            users = cursor.fetchall()
            return users
            
        except Exception as e:
            logging.error(f"❌ Error getting users for daily messages: {e}")
            return []
        finally:
            conn.close()
    
    def get_course_content(self, day_number):
        """Получает контент для конкретного дня"""
        conn = self.get_connection()
        if conn is None:
            return None
        
        cursor = conn.cursor()
        try:
            cursor.execute(
                'SELECT messages FROM course_content WHERE day_number = %s',
                (day_number,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logging.error(f"❌ Error getting course content: {e}")
            return None
        finally:
            conn.close()
    
    def update_user_progress(self, user_id, day_number):
        """Обновляет прогресс пользователя после отправки сообщений"""
        conn = self.get_connection()
        if conn is None:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE course_progress
                SET current_day = %s,
                    last_message_date = CURRENT_TIMESTAMP
                WHERE user_id = %s
            ''', (day_number + 1, user_id))  # Переходим к следующему дню
            
            # Если день 7 завершен, отмечаем курс как неактивный
            if day_number >= 7:
                cursor.execute('''
                    UPDATE course_progress
                    SET is_active = FALSE
                    WHERE user_id = %s
                ''', (user_id,))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"❌ Error updating user progress: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def create_payment(self, user_id, payment_id, amount, currency, payment_method):
        """Создает запись о платеже"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO payments (user_id, payment_id, amount, currency, payment_method, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
            ''', (user_id, payment_id, amount, currency, payment_method))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"❌ Error creating payment: {e}")
            return False
        finally:
            conn.close()

    def update_payment_status(self, payment_id, status):
        """Обновляет статус платежа"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE payments 
                SET status = %s, completed_at = CURRENT_TIMESTAMP 
                WHERE payment_id = %s
            ''', (status, payment_id))
            
            if cursor.rowcount > 0:
                conn.commit()
                # Получаем user_id для отправки уведомления
                cursor.execute('SELECT user_id FROM payments WHERE payment_id = %s', (payment_id,))
                user_id = cursor.fetchone()[0]
                return user_id
            return None
        except Exception as e:
            logging.error(f"❌ Error updating payment: {e}")
            return None
        finally:
            conn.close()

    def get_user_payment_status(self, user_id):
        """Проверяет, есть ли успешный платеж у пользователя"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status FROM payments 
                WHERE user_id = %s AND status = 'success'
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,))
            result = cursor.fetchone()
            return result is not None
        except Exception as e:
            logging.error(f"❌ Error checking payment: {e}")
            return False
        finally:
            conn.close()

    def is_course_active(self, user_id):
        """Проверяет, активен ли курс у пользователя"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT is_active FROM course_progress 
                WHERE user_id = %s 
                AND is_active = TRUE
            ''', (user_id,))
            
            return cursor.fetchone() is not None
        except Exception as e:
            logging.error(f"Error checking course status: {e}")
            return False
        finally:
            conn.close()

db = DatabaseManager()