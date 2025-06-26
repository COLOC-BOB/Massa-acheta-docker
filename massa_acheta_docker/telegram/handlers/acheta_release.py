# massa_acheta_docker/telegram/handlers/acheta_release.py
from loguru import logger
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app_config import app_config
import app_globals
from telegram.menu_utils import build_menu_keyboard

router = Router()

@router.message(Command("acheta_release"))
@logger.catch
async def cmd_acheta_release(message: Message, state: FSMContext) -> None:
    logger.debug(f"[ACHETA_RELEASE] -> cmd_acheta_release")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    if app_globals.latest_acheta_release == app_globals.local_acheta_release:
        update_needed = "👌 <b>No updates needed</b>"
    else:
        update_needed = (
            "☝ <b>Please update your bot</b> – "
            '<a href="https://github.com/COLOC-BOB/Massa-acheta-docker/releases">More info here</a>'
        )

    msg = (
        f"🦗 <b>Latest released ACHETA DOCKER version:</b> {app_globals.latest_acheta_release}\n"
        f"💾 <b>You have version:</b> {app_globals.local_acheta_release}\n"
        f"{update_needed}\n"
        f"⏳ <b>Service checks releases:</b> every {app_config['service']['main_loop_period_min']} minutes"
    )

    try:
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']

        )
    except Exception as e:
        logger.error(f"[ACHETA_RELEASE] Could not send message to user '{message.from_user.id}' in chat '{message.chat.id}' ({str(e)})")
