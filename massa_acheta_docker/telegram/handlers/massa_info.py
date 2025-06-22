# massa_acheta_docker/telegram/handlers/massa_info.py
from loguru import logger
from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from app_config import app_config
import app_globals
from remotes_utils import get_last_seen, get_rewards_mas_day
from telegram.menu_utils import build_menu_keyboard
router = Router()

@router.message(StateFilter(None), Command("massa_info"))
@logger.catch
async def cmd_massa_info(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_massa_info")
    logger.info(f"-> Got '{message.text}' command from '{message.from_user.id}'@'{message.chat.id}'")
    
    # Limite l'usage à ton chat privé
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    wallet_computed_rewards = await get_rewards_mas_day(rolls_number=100)
    info_last_update = await get_last_seen(
        last_time=app_globals.massa_network['values']['last_updated']
    )
    msg = (
        f"💾 <b>Latest released MASSA version:</b> {app_globals.massa_network['values']['latest_release']}\n"
        f"🏃 <b>Current MASSA release:</b> {app_globals.massa_network['values']['current_release']}\n"
        f"🌀 <b>Current cycle:</b> {app_globals.massa_network['values']['current_cycle']:,}\n"
        f"🗞 <b>Roll price:</b> {app_globals.massa_network['values']['roll_price']:,} MAS\n"
        f"💰 <b>Block reward:</b> {app_globals.massa_network['values']['block_reward']:,} MAS\n"
        f"👥 <b>Total stakers:</b> {app_globals.massa_network['values']['total_stakers']:,}\n"
        f"🗞 <b>Total staked rolls:</b> {app_globals.massa_network['values']['total_staked_rolls']:,}\n"        
        f"🪙 <b>Estimated earnings for 100 Rolls</b> ≈ {wallet_computed_rewards:,} MAS / Day\n"
        f"👁 <b>Info updated:</b> {info_last_update}\n"
        f"☝ Service checks updates: every {app_config['service']['massa_network_update_period_min']} mins"
    )
    try:
        await message.reply(
            text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"Could not send message to user '{message.from_user.id}' in chat '{message.chat.id}' ({str(e)})")
