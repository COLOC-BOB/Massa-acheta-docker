from loguru import logger

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from telegram.menu import build_help_text, build_help_keyboard
from aiogram.enums import ParseMode

from app_config import app_config
import app_globals


router = Router()


@router.message(StateFilter(None), Command("start", "help"))
@logger.catch
async def cmd_start(message: Message) -> None:
    logger.debug("-> Enter Def")
    logger.info(f"-> Got '{message.text}' command from '{message.from_user.id}'@'{message.chat.id}'")

    public = message.chat.id != app_globals.bot.ACHETA_CHAT
    t = build_help_text(public)
    keyboard = build_help_keyboard(public)

    try:
        await message.reply(
            text=t,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except BaseException as E:
        logger.error(f"Could not send message to user '{message.from_user.id}' in chat '{message.chat.id}' ({str(E)})")

    return
