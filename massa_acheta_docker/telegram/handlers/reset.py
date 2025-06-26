# massa_acheta_docker/telegram/handlers/reset.py
from loguru import logger
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals
from remotes_utils import save_app_results
from telegram.menu_utils import build_menu_keyboard

class ResetState(StatesGroup):
    reset_sure = State()

router = Router()

@router.message(Command("reset"))
@logger.catch
async def cmd_reset(message: Message, state: FSMContext) -> None:
    logger.debug(f"[RESET] -> cmd_reset")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    msg = (
        "⁉ <b>Please confirm that you actually want to reset the service configuration</b>\n\n"
        "☝ All your configured nodes and wallets will be erased from bot configuration\n\n"
        '⌨ Type <code>I really want to reset all settings</code> to continue or /cancel to quit the scenario'
    )
    try:
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.set_state(ResetState.reset_sure)
    except Exception as e:
        logger.error(f"[RESET] Could not send reset prompt: {e}")
        await state.clear()

@router.message(ResetState.reset_sure, F.text)
@logger.catch
async def do_reset(message: Message, state: FSMContext) -> None:
    logger.debug(f"[RESET] -> do_reset")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    if message.text.strip().upper() != "I REALLY WANT TO RESET ALL SETTINGS":
        msg = (
            "🤚 <b>Reset request rejected</b>\n\n"
            "👉 Use the command menu to learn bot commands"
        )
        try:
            await message.reply(
                text=msg,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as e:
            logger.error(f"[RESET] Could not send reset rejection: {e}")
        await state.clear()
        return

    try:
        async with app_globals.results_lock:
            app_globals.app_results = {}
            save_app_results()
    except Exception as e:
        msg = (
            "‼️ <b>Error: Could not reset configuration</b>\n"
            f"💻 Result: <code>{e}</code>\n"
            "⚠ Try again later or watch logs to check the reason."
        )
    else:
        msg = (
            "👌 <b>Reset done</b>\n"
            "👉 You can check new settings using /view_config command"
        )
    try:
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"[RESET] Could not send reset result: {e}")

    await state.clear()
