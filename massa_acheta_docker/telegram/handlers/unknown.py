from loguru import logger

from aiogram import Router, F
from aiogram.types import Message
from telegram.menu import build_menu_keyboard
from aiogram.fsm.context import FSMContext
from aiogram.utils.formatting import as_list
from aiogram.enums import ParseMode

from app_config import app_config
import app_globals


router = Router()


@router.message(F)
@logger.catch
async def cmd_unknown(message: Message, state: FSMContext) -> None:
    logger.debug("-> Enter Def")
    logger.info(f"-> Got '{message.text}' command from '{message.from_user.id}'@'{message.chat.id}'")

    t = as_list(
        f"⁉ Error: Unknown command",
        "",
        "👉 Use the command menu to explore available commands"
    )
    try:
        public = message.chat.id != app_globals.bot.ACHETA_CHAT
        await message.reply(
            text=t.as_html(),
            reply_markup=build_menu_keyboard(public),
            parse_mode=ParseMode.HTML,
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except BaseException as E:
        logger.error(f"Could not send message to user '{message.from_user.id}' in chat '{message.chat.id}' ({str(E)})")

    await state.clear()
    return
