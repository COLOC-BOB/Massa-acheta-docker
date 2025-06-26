# massa_acheta_docker/telegram/handlers/view_config.py
from loguru import logger
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals
from remotes_utils import get_short_address, get_last_seen
from telegram.menu_utils import build_menu_keyboard
from telegram.keyboards.kb_nodes import kb_nodes

class ConfigViewer(StatesGroup):
    waiting_node_name = State()

router = Router()

@router.message(StateFilter(None), Command("view_config"))
@logger.catch
async def cmd_view_config(message: Message, state: FSMContext) -> None:
    logger.debug(f"[VIEW_CONFIG] -> cmd_view_config")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    if len(app_globals.app_results) == 0:
        text = "⭕ Configuration is empty\n"
        await message.reply(
            text=text,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    # Sélection du node par boutons si plusieurs
    if len(app_globals.app_results) == 1:
        node_name = next(iter(app_globals.app_results))
        await show_node_config(message, node_name, state)
    else:
        await state.set_state(ConfigViewer.waiting_node_name)
        await message.reply(
            text="❓ Select a node to view its configuration, or /cancel to quit:",
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )

@router.message(ConfigViewer.waiting_node_name, F.text)
@logger.catch
async def select_node_to_show(message: Message, state: FSMContext) -> None:
    logger.debug(f"[VIEW_CONFIG] -> select_node_to_show")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text.strip()
    if node_name not in app_globals.app_results:
        await message.reply(
            text=f"‼️ Error: Unknown node \"{node_name}\"\n👉 Try again.",
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    await show_node_config(message, node_name, state)

async def show_node_config(message: Message, node_name: str, state: FSMContext) -> None:
    node = app_globals.app_results[node_name]
    config_html = (
        f"🏠 <b>Node:</b> \"{node_name}\"\n"
        f"📍 <code>{node['url']}</code>\n"
    )

    if len(node['wallets']) == 0:
        config_html += "⭕ No wallets attached\n"
    else:
        config_html += f"👛 {len(node['wallets'])} wallet(s) attached:\n"
        for wallet_address in node['wallets']:
            short_addr = await get_short_address(wallet_address)
            # Affiche l'adresse en texte, SANS lien HTML (donc pas d'aperçu Massa Explorer)
            config_html += f"⦙ … <code>{short_addr}</code>\n"

    config_html += "\n"

    started_str = await get_last_seen(last_time=app_globals.acheta_start_time, show_days=True)
    config_html += (
        f"🏃 <b>Bot started:</b> {started_str}\n\n"
        "👉 Use the command menu to manage settings"
    )

    try:
        await message.reply(
            text=f"📋 <b>Current configuration for node:</b>\n\n{config_html}",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec'],
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"[VIEW_CONFIG] Could not send config: {e}")
    await state.clear()
