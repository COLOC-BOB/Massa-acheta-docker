# massa_acheta_docker/telegram/handlers/view_address.py
from loguru import logger
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
from remotes_utils import get_short_address, get_rewards_mas_day, pull_http_api
from telegram.menu_utils import build_menu_keyboard
import app_globals
import json
from datetime import datetime

class AddressViewer(StatesGroup):
    waiting_wallet_address = State()

router = Router()

async def get_address(wallet_address: str=""):
    logger.debug("-> get_address")
    if not wallet_address.startswith("AU"):
        msg = (
            "‼️ Wrong wallet address format (expected a string starting with AU prefix)\n\n"
            "☝️ Try /view_address and enter a valid AU... address"
        )
        return False, msg

    payload = json.dumps(
        {
            "id": 0,
            "jsonrpc": "2.0",
            "method": "get_addresses",
            "params": [[wallet_address]]
        }
    )

    try:
        wallet_answer = await pull_http_api(
            api_url=app_config['service']['mainnet_rpc_url'],
            api_method="POST",
            api_payload=payload,
            api_root_element="result"
        )
        wallet_result = wallet_answer.get("result", None)
        if not wallet_result or type(wallet_result) != list or not len(wallet_result):
            raise Exception(f"Wrong answer from MASSA node API ({str(wallet_answer)})")
        wallet_result = wallet_result[0]
        wallet_result_address = wallet_result.get("address", None)
        if wallet_result_address != wallet_address:
            raise Exception(f"Bad address received from MASSA node API: '{wallet_result_address}' (expected '{wallet_address}')")
    except Exception as E:
        logger.warning(f"Cannot operate received address result: ({str(E)})")
        short_addr = await get_short_address(wallet_address)
        msg = (
            f"👛 Wallet: <code>{short_addr}</code>\n"
            f"⁉️ Error getting address info for wallet: <code>{short_addr}</code>\n"
            f"💥 Exception: <code>{E}</code>\n"
            f"⚠️ Check wallet address or try later!"
        )
        return False, msg

    # ... (le reste du traitement comme dans ta fonction)

    short_addr = await get_short_address(wallet_address)
    msg = (
        f"👛 Wallet: <code>{short_addr}</code>\n"
        # ... (le reste du message)
    )
    return True, msg

# -------- HANDLERS --------

@router.message(StateFilter(None), Command("view_address"))
@logger.catch
async def cmd_view_address(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_view_address")
    await state.set_state(AddressViewer.waiting_wallet_address)
    await message.reply(
        text="❓ Entrez une adresse AU... à afficher (ou /cancel pour quitter) :",
        parse_mode="HTML",
        reply_markup=None,  # pas de clavier
        request_timeout=app_config['telegram']['sending_timeout_sec']
    )

@router.message(AddressViewer.waiting_wallet_address, F.text)
@logger.catch
async def show_manual_address(message: Message, state: FSMContext) -> None:
    logger.debug("-> show_manual_address")
    wallet_address = message.text.strip()
    if not wallet_address.startswith("AU"):
        await message.reply(
            text="‼️ Merci de saisir une adresse AU... valide.",
            parse_mode="HTML",
            reply_markup=None,
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    r, msg = await get_address(wallet_address=wallet_address)
    try:
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"Could not send message: {e}")

    await state.clear()
