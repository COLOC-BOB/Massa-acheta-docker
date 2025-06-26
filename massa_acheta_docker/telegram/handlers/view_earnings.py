# massa_acheta_docker/telegram/handlers/view_earnings.py
from loguru import logger
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals
from telegram.menu_utils import build_menu_keyboard
from remotes_utils import get_last_seen, get_rewards_mas_day

class EarningsViewer(StatesGroup):
    waiting_rolls_number = State()

router = Router()

@logger.catch
async def get_earnings(rolls_number: int=1):
    logger.debug(f"[VIEW_EARNINGS] -> get_earnings")
    try:
        rolls_number = int(rolls_number)
        total_rolls = app_globals.massa_network['values']['total_staked_rolls']
        if rolls_number < 1 or rolls_number > total_rolls:
            raise Exception
    except Exception:
        msg = (
            f"‼️ Wrong Rolls number value (expected number between 1 and {app_globals.massa_network['values']['total_staked_rolls']})\n\n"
            "☝️ Try /view_earnings <b>Rolls_number</b> command"
        )
        return msg
    else:
        computed_rewards = await get_rewards_mas_day(rolls_number=rolls_number)
        massa_updated = await get_last_seen(
            last_time=app_globals.massa_network['values']['last_updated']
        )
        my_percentage = round(
            (rolls_number / app_globals.massa_network['values']['total_staked_rolls']) * 100,
            6
        )
        msg = (
            f"🏦 Total number of staked Rolls in MASSA Mainnet: {app_globals.massa_network['values']['total_staked_rolls']:,} (updated: {massa_updated})\n\n"
            f"🍰 Your contribution is: {rolls_number:,} Rolls ({my_percentage}%)\n\n"
            f"🪙 Your estimated earnings ≈ {computed_rewards:,} MAS / Day\n\n"
            '👉 <a href="https://docs.massa.net/docs/learn/tokenomics#example-how-to-compute-my-expected-staking-rewards-">More info here</a>'
        )
        return msg

@router.message(StateFilter(None), Command("view_earnings"))
@logger.catch
async def cmd_view_earnings(message: Message, state: FSMContext) -> None:
    logger.debug(f"[VIEW_EARNINGS] -> cmd_view_earnings")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    message_list = message.text.split()
    if len(message_list) < 2:
        msg = (
            "❓ Please answer with a certain number of staked rolls:\n\n"
            f"☝️ The answer must be an integer between 1 and {app_globals.massa_network['values']['total_staked_rolls']}\n\n"
            "👉 Use /cancel to quit the scenario"
        )
        try:
            await message.reply(
                text=msg,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
            await state.set_state(EarningsViewer.waiting_rolls_number)
        except Exception as e:
            logger.error(f"[VIEW_EARNINGS] Could not send message: {e}")
        return

    rolls_number = message_list[1]
    msg = await get_earnings(rolls_number=rolls_number)
    try:
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"[VIEW_EARNINGS] Could not send message: {e}")

    await state.clear()
    return

@router.message(EarningsViewer.waiting_rolls_number, F.text)
@logger.catch
async def show_earnings(message: Message, state: FSMContext) -> None:
    logger.debug(f"[VIEW_EARNINGS] -> show_earnings")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    rolls_number = "0"
    command_list = message.text.split()
    for cmd in command_list:
        if cmd.isdigit():
            rolls_number = cmd
            break

    msg = await get_earnings(rolls_number=rolls_number)
    try:
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"[VIEW_EARNINGS] Could not send message: {e}")

    await state.clear()
    return
