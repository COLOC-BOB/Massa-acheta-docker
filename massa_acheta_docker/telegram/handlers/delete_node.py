# massa_acheta_docker/telegram/handlers/delete_node.py
from loguru import logger
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals

from telegram.keyboards.kb_nodes import kb_nodes
from telegram.menu_utils import build_menu_keyboard
from remotes_utils import get_short_address, save_app_results

class NodeRemover(StatesGroup):
    waiting_node_name = State()

router = Router()

@router.message(Command("delete_node"))
@logger.catch
async def cmd_delete_node(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_delete_node")
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

    await message.reply(
        text="❓ Tap the node to select or /cancel to quit the scenario:",
        parse_mode="HTML",
        reply_markup=kb_nodes(),
        request_timeout=app_config['telegram']['sending_timeout_sec']
    )
    await state.set_state(NodeRemover.waiting_node_name)

@router.message(NodeRemover.waiting_node_name, F.text)
@logger.catch
async def delete_node(message: Message, state: FSMContext) -> None:
    logger.debug("-> delete_node")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text.strip()

    if node_name not in app_globals.app_results:
        await message.reply(
            text=f"‼️ <b>Error:</b> Unknown node \"{node_name}\"\n\n👉 Try /delete_node to delete another node or use the command menu for help",
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    try:
        async with app_globals.results_lock:
            app_globals.app_results.pop(node_name, None)
            save_app_results()
    except Exception as E:
        logger.error(f"Cannot remove node '{node_name}': ({str(E)})")
        short_name = await get_short_address(node_name)
        await message.reply(
            text=(
                f"‼️ <b>Error:</b> Could not delete node <code>{short_name}</code>\n"
                f"💻 Result: <code>{E}</code>\n"
                "⚠ Try again later or watch logs to check the reason."
            ),
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    else:
        logger.info(f"Successfully removed node '{node_name}'")
        short_name = await get_short_address(node_name)
        await message.reply(
            text=(
                f"👌 Successfully removed node <code>{short_name}</code>\n"
                "👉 You can check new settings using /view_config command"
            ),
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    await state.clear()
