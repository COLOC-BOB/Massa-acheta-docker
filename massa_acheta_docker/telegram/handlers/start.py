# massa_acheta_docker/telegram/handlers/start.py
from loguru import logger
from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app_config import app_config
import app_globals
from telegram.menu_utils import build_menu_keyboard

router = Router()

@router.message(StateFilter(None), Command("start"))
@logger.catch
async def cmd_start(message: Message, state: FSMContext) -> None:
    logger.debug(f"[START] -> cmd_start")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    t = (
        "👋 <b>Welcome to your private MASSA Acheta bot</b>!\n\n"
        "Use the menu below to get started.\n"
        "If you need help, use /help or the command menu."
    )
    keyboard = build_menu_keyboard()
    
    try:
        await message.reply(
            text=t,
            parse_mode="HTML",
            reply_markup=keyboard,
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"[START] Could not send start message: {e}")
