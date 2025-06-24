# massa_acheta_docker/telegram/handlers/add_wallet.py
from loguru import logger
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from collections import deque

from app_config import app_config
import app_globals

from remotes.wallet import check_wallet
from telegram.keyboards.kb_nodes import kb_nodes
from remotes_utils import get_short_address, save_app_results
from telegram.menu_utils import build_menu_keyboard

class WalletAdder(StatesGroup):
    waiting_node_name = State()
    waiting_wallet_address = State()

router = Router()

@router.message(Command("add_wallet"))
@logger.catch
async def cmd_add_wallet(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_add_wallet")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    if len(app_globals.app_results) == 0:
        try:
            await message.reply(
                text="⭕ Node list is empty\n\n👉 Try /add_node to add a node or use the command menu for help",
                parse_mode="HTML",
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as E:
            logger.error(f"Could not send message: {E}")
        await state.clear()
        return

    try:
        await state.set_state(WalletAdder.waiting_node_name)
        await message.reply(
            text="❓ Tap the node to select or /cancel to quit the scenario:",
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as E:
        logger.error(f"Could not send message: {E}")
        await state.clear()

@router.message(WalletAdder.waiting_node_name, F.text)
@logger.catch
async def input_wallet_to_add(message: Message, state: FSMContext) -> None:
    logger.debug("-> input_wallet_to_add")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text.strip()
    if node_name not in app_globals.app_results:
        try:
            await message.reply(
                text=f"‼️ <b>Error:</b> Unknown node {node_name}\n\n👉 Try /add_wallet to add another wallet or use the command menu for help",
                parse_mode="HTML",
                reply_markup=kb_nodes(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as E:
            logger.error(f"Could not send message: {E}")
        await state.clear()
        return

    try:
        await state.set_state(WalletAdder.waiting_wallet_address)
        await state.set_data(data={"node_name": node_name})
        await message.reply(
            text=(
                "❓ Please enter MASSA wallet address with leading <u>AU</u> prefix or /cancel to quit the scenario:"
            ),
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as E:
        logger.error(f"Could not send message: {E}")
        await state.clear()

@router.message(WalletAdder.waiting_wallet_address, F.text.startswith("AU"))
@logger.catch
async def add_wallet(message: Message, state: FSMContext) -> None:
    logger.debug("-> add_wallet")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    try:
        user_state = await state.get_data()
        node_name = user_state['node_name']
        wallet_address = message.text.strip()
    except Exception as E:
        logger.error(f"Cannot read state: {E}")
        await state.clear()
        return

    # Si déjà attaché
    if wallet_address in app_globals.app_results[node_name]['wallets']:
        short_addr = await get_short_address(wallet_address)
        try:
            await message.reply(
                text=(
                    f"‼️ <b>Error:</b> Wallet <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a> already attached to node {node_name}\n"
                    "👉 Try /add_wallet to add another wallet or use the command menu for help"
                ),
                parse_mode="HTML",
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as E:
            logger.error(f"Could not send message: {E}")
        await state.clear()
        return

    # Ajout du wallet
    try:
        async with app_globals.results_lock:
            app_globals.app_results[node_name]['wallets'][wallet_address] = {
                'final_balance': 0,
                'candidate_rolls': 0,
                'active_rolls': 0,
                'missed_blocks': 0,
                'last_cycle': 0,
                'last_ok_count': 0,
                'last_nok_count': 0,
                'last_status': "unknown",
                'last_update': 0,
                'last_result': {"unknown": "Never updated before"},
                'stat': deque(
                    maxlen=int(
                        24 * 60 / app_config['service']['main_loop_period_min']
                    )
                )
            }
            save_app_results()

    except Exception as E:
        short_addr = await get_short_address(wallet_address)
        try:
            await message.reply(
                text=(
                    f"‼️ <b>Error:</b> Could not add wallet <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a> to node {node_name}\n"
                    f"💻 Result: <code>{E}</code>\n"
                    "⚠ Try again later or watch logs to check the reason."
                ),
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as e2:
            logger.error(f"Could not send message: {e2}")
        await state.clear()
        return

    # Succès
    short_addr = await get_short_address(wallet_address)
    try:
        await message.reply(
            text=(
                f"👌 Successfully added wallet: <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a>\n"
                f"🏠 Node: {node_name}\n"
                f"📍 <code>{app_globals.app_results[node_name]['url']}</code>\n\n"
                "👁 You can check new settings using /view_config command\n\n"
                "☝ Please note that info for this wallet will be updated a bit later!"
            ),
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec'],
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Could not send message: {e}")

    await state.clear()

    if app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] != True:
        async with app_globals.results_lock:
            await asyncio.gather(check_wallet(node_name=node_name, wallet_address=wallet_address))
