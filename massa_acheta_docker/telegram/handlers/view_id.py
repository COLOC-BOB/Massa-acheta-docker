# massa_acheta_docker/telegram/handlers/view_id.py
from loguru import logger
from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app_config import app_config
import app_globals
from telegram.menu_utils import build_menu_keyboard

router = Router()

@router.message(StateFilter(None), Command("view_id"))
@logger.catch
async def cmd_view_id(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_view_id")
    user_id = message.from_user.id
    chat_id = message.chat.id

    text = (
        f"👤 <b>User ID:</b> <code>{user_id}</code>\n"
        f"💬 <b>Chat ID:</b> <code>{chat_id}</code>"
    )

    try:
        await message.reply(
            text=text,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
              request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"Could not send message to user '{user_id}' in chat '{chat_id}' ({str(e)})")
