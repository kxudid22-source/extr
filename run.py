import os
import sys
import threading
import asyncio
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_server():
    from server.main import main
    main()

def run_bot():
    from bot.main import main as bot_main
    asyncio.run(bot_main())

if __name__ == "__main__":
    t1 = threading.Thread(target=run_server, daemon=True)
    t1.start()
    run_bot()
