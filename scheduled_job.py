#!/usr/bin/env python3
import asyncio
import logging
from daily_messages import send_daily_messages

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Запускает отправку ежедневных сообщений"""
    try:
        await send_daily_messages()
        print("✅ Daily messages sent successfully")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    asyncio.run(main())