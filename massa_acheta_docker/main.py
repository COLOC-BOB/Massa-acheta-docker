# massa_acheta_docker/main.py
from loguru import logger
logger.add(
    "main.log",
    format="\"{time}\", \"{level}\", \"{file}:{line}\", \"{module}:{function}\", \"{message}\"",
    level="INFO",
    rotation="1 week",
    compression="zip",
    enqueue=True,
    backtrace=True,
    diagnose=True
)

import asyncio
from pathlib import Path
from sys import exit as sys_exit

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app_config import app_config
import app_globals

from remotes.monitor import monitor as remote_monitor
from remotes.massa import massa as remote_massa
from remotes.heartbeat import heartbeat as remote_heartbeat

from telegram.queue import queue_telegram_message, operate_telegram_queue

from telegram.handlers import start
from telegram.handlers import cancel
from telegram.handlers import view_config, view_node, view_wallet, view_address, view_credits, view_earnings, view_id, chart_wallet
from telegram.handlers import add_node, add_wallet
from telegram.handlers import delete_node, delete_wallet
from telegram.handlers import massa_info, massa_chart, acheta_release
from telegram.handlers import reset
from telegram.handlers import unknown
from telegram.menu import router as menu_router
from telegram.handlers import help
from telegram.handlers import watchers_menu

from remotes_utils import save_app_stat, save_app_results, update_deferred_credits_from_node

from watchers.blocks import watch_blocks
from watchers.deferred_credits import watch_deferred_credits
from watchers.rolls import watch_rolls
from watchers.balance import watch_balance
from watchers.missed_blocks import watch_missed_blocks
from watchers.operations import watch_operations

async def deferred_credits_auto_refresh_loop():
    while True:
        try:
            logger.info(f"[MAIN] Refresh deferred_credits.json depuis le node Massa")
            await asyncio.to_thread(update_deferred_credits_from_node)  # Si la fonction est sync ! Sinon : await update_deferred_credits_from_node()
        except Exception as e:
            logger.error(f"[MAIN] Refresh deferred_credits error: {str(e)}")
        await asyncio.sleep(600)  # 10 minutes

def format_start_message():
    nodes_list = []
    if len(app_globals.app_results) == 0:
        nodes_list.append("\n⭕ Node list is empty")
    else:
        for node_name in app_globals.app_results:
            nodes_list.append(f"\n🏠 Node: \"{node_name}\"")
            nodes_list.append(f"📍 {app_globals.app_results[node_name]['url']}")
            nodes_list.append(f"👛 {len(app_globals.app_results[node_name]['wallets'])} wallet(s) attached")
    message_html = (
        "<b>🔆 Service successfully started to watch the following nodes:</b>\n"
        + "\n".join(nodes_list) +
        "\n\n👉 Use the command menu to learn bot commands" +
        f"\n\n⏳ Main loop period: <b>{app_config['service']['main_loop_period_min']}</b> minutes" +
        f"\n\n⚡ Probe timeout: <b>{app_config['service']['http_probe_timeout_sec']}</b> seconds"
    )
    return message_html

@logger.catch
async def main() -> None:
    logger.debug(f"[MAIN] -> main")

    # ----------- INSTANCIATION DU BOT & DU DISPATCHER ---------------
    tg_bot = Bot(
        token=app_globals.ACHETA_KEY,
        parse_mode=ParseMode.HTML,
    )
    tg_dp = Dispatcher()
    # Optionnel : met dans app_globals si tu veux du global partout :
    app_globals.tg_bot = tg_bot
    app_globals.tg_dp = tg_dp
    # ---------------------------------------------------------------

    logger.info(f"[MAIN] Private menu applied.")
    await queue_telegram_message(message_text=format_start_message())

    try:
        asyncio.create_task(operate_telegram_queue())
        asyncio.create_task(remote_monitor())
        asyncio.create_task(remote_massa())
        asyncio.create_task(remote_heartbeat())
        asyncio.create_task(deferred_credits_auto_refresh_loop())
        # WATCHERS
        asyncio.create_task(watch_blocks())
        asyncio.create_task(watch_deferred_credits())
        asyncio.create_task(watch_rolls())
        asyncio.create_task(watch_balance())
        asyncio.create_task(watch_missed_blocks())
        asyncio.create_task(watch_operations())
        # ROUTEURS HANDLERS
        tg_dp.include_router(help.router)
        tg_dp.include_router(start.router)
        tg_dp.include_router(cancel.router)
        tg_dp.include_router(view_config.router)
        tg_dp.include_router(view_node.router)
        tg_dp.include_router(view_wallet.router)
        tg_dp.include_router(chart_wallet.router)
        tg_dp.include_router(view_address.router)
        tg_dp.include_router(view_credits.router)
        tg_dp.include_router(view_earnings.router)
        tg_dp.include_router(view_id.router)
        tg_dp.include_router(add_node.router)
        tg_dp.include_router(add_wallet.router)
        tg_dp.include_router(delete_node.router)
        tg_dp.include_router(delete_wallet.router)
        tg_dp.include_router(massa_info.router)
        tg_dp.include_router(massa_chart.router)
        tg_dp.include_router(acheta_release.router)
        tg_dp.include_router(reset.router)
        tg_dp.include_router(menu_router)  
        tg_dp.include_router(unknown.router)
        tg_dp.include_router(watchers_menu.router)
        
        await tg_bot.delete_webhook(drop_pending_updates=True)
        await tg_dp.start_polling(tg_bot)

    except BaseException as E:
        logger.error(f"[MAIN] Exception {str(E)} ({E})")
    finally:
        logger.error(f"[MAIN] <- Quit Def")

    return

if __name__ == "__main__":
    logger.info(f"[MAIN] MASSA Acheta started at {app_globals.acheta_start_time}")

    try:
        asyncio.run(main())
    except BaseException as E:
        logger.error(f"[MAIN] Exception {str(E)} ({E})")
    finally:
        save_app_results()
        save_app_stat()
        logger.critical(f"[MAIN] Service terminated")
        sys_exit()
