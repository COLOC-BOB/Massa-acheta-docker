# massa_acheta_docker/telegram/handlers/view_node.py
from loguru import logger
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals

from telegram.keyboards.kb_nodes import kb_nodes
from telegram.menu_utils import build_menu_keyboard
from remotes_utils import get_last_seen, get_short_address, get_duration

class NodeViewer(StatesGroup):
    waiting_node_name = State()

router = Router()

@router.message(StateFilter(None), Command("view_node"))
@logger.catch
async def cmd_view_node(message: Message, state: FSMContext) -> None:
    logger.debug(f"[VIEW_NODE] -> cmd_view_node")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    if len(app_globals.app_results) == 0:
        text = (
            "⭕ Node list is empty\n\n"
            "👉 Use the command menu to learn how to add a node to bot"
        )
        try:
            await message.reply(
                text=text,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as e:
            logger.error(f"[VIEW_NODE] Could not send message: {e}")
        await state.clear()
        return

    # Un seul node : saute la sélection, go direct
    if len(app_globals.app_results) == 1:
        node_name = next(iter(app_globals.app_results))
        await show_node_info(message, state, node_name)
        return

    # Sinon propose la sélection
    text = "👉 Tap the node to view or /cancel to quit the scenario"
    try:
        await message.reply(
            text=text,
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.set_state(NodeViewer.waiting_node_name)
    except Exception as e:
        logger.error(f"[VIEW_NODE] Could not send message: {e}")
        await state.clear()

@router.message(NodeViewer.waiting_node_name, F.text)
@logger.catch
async def show_node(message: Message, state: FSMContext) -> None:
    logger.debug(f"[VIEW_NODE] -> show_node (button)")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text.strip()
    await show_node_info(message, state, node_name)

async def show_node_info(message: Message, state: FSMContext, node_name: str) -> None:
    if node_name not in app_globals.app_results:
        text = (
            f"‼️ Error: Unknown node \"{node_name}\"\n\n"
            "👉 Try /view_node to view another node or use the command menu for help"
        )
        try:
            await message.reply(
                text=text,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as e:
            logger.error(f"[VIEW_NODE] Could not send message: {e}")
        await state.clear()
        return

    node_data = app_globals.app_results[node_name]
    if len(node_data['wallets']) == 0:
        wallets_attached = "⭕ No wallets attached"
    else:
        wallets_attached = f"👛 Wallets attached: {len(node_data['wallets'])}"

    last_seen = await get_last_seen(last_time=node_data['last_update'])
    node_uptime = await get_duration(start_time=node_data.get('start_time', 0), show_days=True)

    # OFFLINE
    if node_data['last_status'] != True:
        node_status = f"☠️ Status: Offline (last seen: {last_seen})\n"
        last_result = node_data.get('last_result', {})
        last_result_str = str(last_result)
        text = (
            f"🏠 <b>Node:</b> {node_name}\n"
            f"📍 <code>{node_data['url']}</code>\n"
            f"{wallets_attached}\n"
            f"{node_status}\n"
            f"💻 <b>Result:</b> <code>{last_result_str}</code>\n"
            f"☝️ Service checks updates: every {app_config['service']['main_loop_period_min']} minutes"
        )
    # ONLINE
    else:
        node_status = f"🌿 Status: Online (uptime {node_uptime})\n"
        last_result = node_data.get('last_result', {})
        node_id = last_result.get("node_id", "Not known")
        node_ip = last_result.get("node_ip", "Not known")
        node_version = last_result.get("version", "Not known")
        latest_release = app_globals.massa_network['values']['latest_release']
        node_update_needed = f"❗ Update to {latest_release}" if node_version != latest_release and latest_release else "(latest)"
        current_cycle = node_data.get('last_cycle', "-")
        chain_id = node_data.get('last_chain_id', "-")

        network_stats = last_result.get('network_stats', {})
        in_connection_count = network_stats.get("in_connection_count", 0)
        out_connection_count = network_stats.get("out_connection_count", 0)
        known_peer_count = network_stats.get("known_peer_count", 0)
        banned_peer_count = network_stats.get("banned_peer_count", 0)

        text = (
            f"🏠 <b>Node:</b> {node_name}\n"
            f"📍 <code>{node_data['url']}</code>\n"
            f"{wallets_attached}\n"
            f"{node_status}\n"
            f"🆔: <code>{await get_short_address(node_id)}</code>\n"
            f"🎯 Routable IP: <code>{node_ip}</code>\n"
            f"💾 Release: <code>{node_version}</code> {node_update_needed}\n"
            f"🌀 Cycle: <code>{current_cycle}</code>\n"
            f"↔ In / Out connections: {in_connection_count} / {out_connection_count}\n"
            f"🙋 Known / Banned peers: {known_peer_count} / {banned_peer_count}\n"
            f"🔗 Chain ID: <code>{chain_id}</code>\n"
            f"☝️ Service checks updates: every {app_config['service']['main_loop_period_min']} minutes"
        )

    try:
        await message.reply(
            text=text,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"[VIEW_NODE] Could not send message: {e}")

    await state.clear()
