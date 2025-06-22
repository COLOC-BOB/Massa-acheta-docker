# massa_acheta_docker/telegram/handlers/unknown.py
from loguru import logger
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext


from app_config import app_config
import app_globals
from telegram.menu_utils import build_menu_keyboard

router = Router()

@router.message(F)
@logger.catch
async def cmd_unknown(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_unknown")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    t = (
        "⁉️ <b>Error: Unknown command</b>\n"
        "👉 Use the command menu to explore available commands"
    )
    keyboard = build_menu_keyboard()

    try:
        await message.reply(
            text=t,
            reply_markup=keyboard,
            parse_mode="HTML",
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"Could not send unknown command message: {e}")

    await state.clear()
