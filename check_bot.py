import requests
import subprocess
import sys
import os

def is_bot_alive():
    """Проверяет, отвечает ли сайт бота"""
    try:
        response = requests.get('https://olesia2202.pythonanywhere.com/health', timeout=10)
        return response.status_code == 200
    except:
        return False

def start_bot():
    """Запускает бота в фоновом режиме"""
    bot_script = '/home/Olesia2202/my-bot/bot.py'
    # Запускаем в фоне с nohup, чтобы не зависеть от сессии
    cmd = f'cd ~/my-bot && source ~/.virtualenvs/mybotenv/bin/activate && python {bot_script}'
    subprocess.Popen(['bash', '-c', cmd])

def main():
    if not is_bot_alive():
        print("🤖 Бот не отвечает, запускаю...")
        start_bot()
        print("✅ Бот запущен")
    else:
        print("✅ Бот уже работает")

if __name__ == '__main__':
    main()