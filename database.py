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
                    registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
                INSERT INTO users (user_id, username, first_name, last_name) 
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO NOTHING
            ''', (user_id, username, first_name, last_name))
            
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"❌ Error creating user: {e}")
            return False
        finally:
            conn.close()


db = DatabaseManager()