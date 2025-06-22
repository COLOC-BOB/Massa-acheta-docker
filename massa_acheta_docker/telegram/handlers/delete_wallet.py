# massa_acheta_docker/telegram/handlers/delete_wallet.py
from loguru import logger
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals

from telegram.keyboards.kb_nodes import kb_nodes
from telegram.keyboards.kb_wallets import kb_wallets
from remotes_utils import get_short_address, save_app_results
from telegram.menu_utils import build_menu_keyboard

class WalletRemover(StatesGroup):
    waiting_node_name = State()
    waiting_wallet_address = State()

router = Router()

@router.message(Command("delete_wallet"))
@logger.catch
async def cmd_delete_wallet(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_delete_wallet")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    if len(app_globals.app_results) == 0:
        await message.reply(
            text="⭕ Node list is empty\n\n👉 Use the command menu to learn how to add a node to bot",
            parse_mode="HTML",
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    await state.set_state(WalletRemover.waiting_node_name)
    await message.reply(
        text="❓ Tap the node to select or /cancel to quit the scenario:",
        parse_mode="HTML",
        reply_markup=kb_nodes(),
        request_timeout=app_config['telegram']['sending_timeout_sec']
    )

@router.message(WalletRemover.waiting_node_name, F.text)
@logger.catch
async def select_wallet_to_delete(message: Message, state: FSMContext) -> None:
    logger.debug("-> select_wallet_to_delete")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text.strip()
    if node_name not in app_globals.app_results:
        await message.reply(
            text=f"‼️ <b>Error:</b> Unknown node \"{node_name}\"\n👉 Try /delete_wallet to delete another wallet or use the command menu for help",
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    if len(app_globals.app_results[node_name]['wallets']) == 0:
        await message.reply(
            text=f"⭕ No wallets attached to node \"{node_name}\"\n👉 Try /add_wallet to add a wallet or use the command menu for help",
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    await state.set_state(WalletRemover.waiting_wallet_address)
    await state.set_data(data={"node_name": node_name})
    await message.reply(
        text="❓ Tap the wallet to select or /cancel to quit the scenario:",
        parse_mode="HTML",
        reply_markup=kb_wallets(node_name=node_name),
        request_timeout=app_config['telegram']['sending_timeout_sec']
    )

@router.message(WalletRemover.waiting_wallet_address, F.text.startswith("AU"))
@logger.catch
async def delete_wallet(message: Message, state: FSMContext) -> None:
    logger.debug("-> delete_wallet")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    try:
        user_state = await state.get_data()
        node_name = user_state['node_name']
        wallet_address = message.text.strip()
    except Exception as e:
        logger.error(f"Cannot read state: {e}")
        await state.clear()
        return

    if wallet_address not in app_globals.app_results[node_name]['wallets']:
        short_addr = await get_short_address(wallet_address)
        await message.reply(
            text=(
                f"‼️ <b>Error:</b> Wallet <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a> "
                f"is not attached to node \"{node_name}\"\n"
                "👉 Try /delete_wallet to delete another wallet or use the command menu for help"
            ),
            parse_mode="HTML",
            reply_markup=kb_wallets(node_name=node_name),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    try:
        async with app_globals.results_lock:
            app_globals.app_results[node_name]['wallets'].pop(wallet_address, None)
            save_app_results()
    except Exception as e:
        logger.error(f"Cannot remove wallet '{wallet_address}' from node '{node_name}': ({str(e)})")
        short_addr = await get_short_address(wallet_address)
        short_node = await get_short_address(node_name)
        await message.reply(
            text=(
                f"‼️ <b>Error:</b> Could not delete wallet "
                f"<a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a> "
                f"from node <code>{short_node}</code>\n"
                f"💻 Result: <code>{e}</code>\n"
                "⚠ Try again later or watch logs to check the reason."
            ),
            parse_mode="HTML",
            reply_markup=kb_wallets(node_name=node_name),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    else:
        logger.info(f"Successfully removed wallet '{wallet_address}' from node '{node_name}'")
        short_addr = await get_short_address(wallet_address)
        short_node = await get_short_address(node_name)
        await message.reply(
            text=(
                f"👌 Successfully removed wallet "
                f"<a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a> "
                f"from node <code>{short_node}</code>\n"
                "👉 You can check new settings using /view_config command"
            ),
            parse_mode="HTML",
            reply_markup=kb_wallets(node_name=node_name),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    await state.clear()
