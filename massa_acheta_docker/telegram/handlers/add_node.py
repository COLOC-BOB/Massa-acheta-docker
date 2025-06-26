# massa_acheta_docker/telegram/handlers/add_node.py
from loguru import logger
import asyncio
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals
from remotes.node import check_node
from telegram.menu_utils import build_menu_keyboard

class NodeAdder(StatesGroup):
    waiting_node_name = State()
    waiting_node_url = State()

router = Router()

@router.message(Command("add_node"))
@logger.catch
async def cmd_add_node(message: Message, state: FSMContext) -> None:
    logger.debug(f"[ADD_NODE] -> cmd_add_node")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return
    await state.set_state(NodeAdder.waiting_node_name)
    try:
        await message.reply(
            text="❓ Please enter a short name for the new node (nickname) or /cancel to quit the scenario:",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"[ADD_NODE] Could not send message: {e}")
        await state.clear()

@router.message(NodeAdder.waiting_node_name, F.text)
@logger.catch
async def input_nodename_to_add(message: Message, state: FSMContext) -> None:
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text.strip()
    if node_name in app_globals.app_results:
        await message.reply(
            text=f"‼️ <b>Error:</b> Node with nickname {node_name} already exists\n👉 Try /add_node to add another node\n",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    await state.set_state(NodeAdder.waiting_node_url)
    await state.set_data(data={"node_name": node_name})
    try:
        await message.reply(
            text=(
                f"❓ Please enter API URL for the new node {node_name} with leading http(s)://... or /cancel to quit.\n"
                "☝ Typically API URL looks like: http://ip.ad.dre.ss:33035/api/v2"
            ),
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"[ADD_NODE] Could not send message: {e}")
        await state.clear()

@router.message(NodeAdder.waiting_node_url, F.text.startswith("http"))
@logger.catch
async def add_node(message: Message, state: FSMContext) -> None:
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    try:
        user_state = await state.get_data()
        node_name = user_state['node_name']
        node_url = message.text.strip()
    except Exception as e:
        logger.error(f"[ADD_NODE] Cannot read state: {e}")
        await state.clear()
        return

    try:
        # Ajout du node à la config
        async with app_globals.results_lock:
            app_globals.app_results[node_name] = {
                'url': node_url,
                'last_status': "unknown",
                'last_update': 0,
                'start_time': 0,
                'last_result': {"unknown": "Never updated before"},
                'wallets': {}
            }
        await message.reply(
            text=(
                f"✅ Successfully added node <b>{node_name}</b> with API URL: <code>{node_url}</code>\n"
                "👁 Please note that bot will update info for this node a bit later.\n"
                "☝️ You can add wallet to node using /add_wallet command."
            ),
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"[ADD_NODE] Cannot add node: {e}")
        await message.reply(
            text=(
                f"‼️ Error: Could not add node <b>{node_name}</b> with API URL {node_url}\n"
                f"💻 Result: <code>{e}</code>"
            ),
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    await state.clear()

    # Lance check_node pour peupler les infos du node tout de suite
    try:
        if app_globals.app_results[node_name]['last_status'] != True:
            async with app_globals.results_lock:
                await asyncio.gather(check_node(node_name=node_name))
    except Exception as e:
        logger.warning(f"[ADD_NODE] check_node failed after node add: {e}")
