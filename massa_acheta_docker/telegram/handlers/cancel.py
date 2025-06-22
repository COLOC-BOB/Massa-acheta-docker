# massa_acheta_docker/telegram/handlers/cancel.py
from loguru import logger
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from app_config import app_config
import app_globals
from telegram.menu_utils import build_menu_keyboard 

router = Router()

@router.message(Command("cancel"))
@logger.catch
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_cancel")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    try:
        await state.clear()
        await message.reply(
            text="❌ Action cancelled!",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"Could not send cancel message: {e}")
