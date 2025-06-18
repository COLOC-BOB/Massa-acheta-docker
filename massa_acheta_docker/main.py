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
from aiogram.utils.formatting import as_list
from telegram.menu import get_bot_commands
from pathlib import Path
from sys import exit as sys_exit

from app_config import app_config
import app_globals

from remotes.monitor import monitor as remote_monitor
from remotes.massa import massa as remote_massa
from remotes.heartbeat import heartbeat as remote_heartbeat

from telegram.queue import queue_telegram_message, operate_telegram_queue

from telegram.handlers import start
from telegram.handlers import cancel
from telegram.handlers import view_config, view_node, view_wallet, view_address, clean_address, view_credits, view_earnings, view_id, chart_wallet
from telegram.handlers import add_node, add_wallet
from telegram.handlers import delete_node, delete_wallet
from telegram.handlers import massa_info, massa_chart, acheta_release
from telegram.handlers import reset
from telegram.handlers import unknown

from tools import save_app_stat, save_app_results


@logger.catch
async def main() -> None:
    logger.debug(f"-> Enter Def")

    public_obj = Path("public")
    public = public_obj.exists()
    if not public:
        logger.info(f"No file '{public_obj}' exists. Private menu applied.")
    else:
        logger.info(f"File '{public_obj}' exists. Public menu applied.")

    bot_commands = get_bot_commands(public)

    await app_globals.tg_bot.set_my_commands(bot_commands)

    nodes_list = []

    if len(app_globals.app_results) == 0:
        nodes_list.append("\n⭕ Node list is empty")
    else:
        for node_name in app_globals.app_results:
            nodes_list.append(f"\n🏠 Node: \"{node_name}\"")
            nodes_list.append(f"📍 {app_globals.app_results[node_name]['url']}")
            nodes_list.append(f"👛 {len(app_globals.app_results[node_name]['wallets'])} wallet(s) attached")


    t = as_list(
        "🔆 Service successfully started to watch the following nodes:",
        *nodes_list,
        "",
        "👉 Use the command menu to learn bot commands",
        "",
        f"⏳ Main loop period: {app_config['service']['main_loop_period_min']} minutes",
        f"⚡ Probe timeout: {app_config['service']['http_probe_timeout_sec']} seconds"
    )
    await queue_telegram_message(message_text=t.as_html())

    try:
        asyncio.create_task(operate_telegram_queue())
        asyncio.create_task(remote_monitor())
        asyncio.create_task(remote_massa())
        asyncio.create_task(remote_heartbeat())


        app_globals.tg_dp.include_router(start.router)

        app_globals.tg_dp.include_router(cancel.router)

        app_globals.tg_dp.include_router(view_config.router)
        app_globals.tg_dp.include_router(view_node.router)
        app_globals.tg_dp.include_router(view_wallet.router)
        app_globals.tg_dp.include_router(chart_wallet.router)
        app_globals.tg_dp.include_router(view_address.router)
        app_globals.tg_dp.include_router(clean_address.router)
        app_globals.tg_dp.include_router(view_credits.router)
        app_globals.tg_dp.include_router(view_earnings.router)
        app_globals.tg_dp.include_router(view_id.router)

        app_globals.tg_dp.include_router(add_node.router)
        app_globals.tg_dp.include_router(add_wallet.router)

        app_globals.tg_dp.include_router(delete_node.router)
        app_globals.tg_dp.include_router(delete_wallet.router)

        app_globals.tg_dp.include_router(massa_info.router)
        app_globals.tg_dp.include_router(massa_chart.router)
        app_globals.tg_dp.include_router(acheta_release.router)

        app_globals.tg_dp.include_router(reset.router)

        app_globals.tg_dp.include_router(unknown.router)

        await app_globals.tg_bot.delete_webhook(drop_pending_updates=True)
        await app_globals.tg_dp.start_polling(app_globals.tg_bot)

    except BaseException as E:
        logger.error(f"Exception {str(E)} ({E})")
    
    finally:
        logger.error(f"<- Quit Def")

    return
    



if __name__ == "__main__":
    logger.info(f"MASSA Acheta started at {app_globals.acheta_start_time}")

    try:
        asyncio.run(main())

    except BaseException as E:
        logger.error(f"Exception {str(E)} ({E})")
    
    finally:
        save_app_results()
        save_app_stat()

        logger.critical("Service terminated")
        sys_exit()
