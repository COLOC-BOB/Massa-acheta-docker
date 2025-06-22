# massa_acheta_docker/telegram/handlers/view_credits.py

from loguru import logger
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals
from remotes_utils import get_short_address, t_now
from telegram.menu_utils import build_menu_keyboard
from telegram.keyboards.kb_nodes import kb_nodes
from telegram.keyboards.kb_wallets import kb_wallets

class CreditsViewer(StatesGroup):
    waiting_node_name = State()
    waiting_wallet_address = State()

router = Router()

@logger.catch
async def get_credits(wallet_address: str=""):
    logger.debug("-> get_credits")

    if not wallet_address.startswith("AU"):
        msg = (
            "‼️ Wrong wallet address format (expected a string starting with AU prefix)\n\n"
            "☝️ Try /view_credits with <b>AU...</b> wallet address"
        )
        return False, msg

    wallet_credits = app_globals.deferred_credits.get(wallet_address, None)
    if not wallet_credits or not isinstance(wallet_credits, list) or len(wallet_credits) == 0:
        short_addr = await get_short_address(wallet_address)
        msg = (
            f"👛 Wallet: <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a>\n"
            "🙅 No deferred credits available"
        )
        return False, msg

    deferred_credits_html = ["💳 <b>Deferred credits:</b>\n"]
    now_unix = int(await t_now())
    for wallet_credit in wallet_credits:
        try:
            credit_amount = float(wallet_credit.get("amount", 0))
            credit_amount = round(credit_amount, 4)
            credit_slot = wallet_credit.get("slot", None)
            credit_period = credit_slot.get("period", None) if credit_slot else None
            credit_unix = 1705312800 + (int(credit_period) * 16) if credit_period is not None else None
            credit_date = datetime.utcfromtimestamp(credit_unix).strftime("%b %d, %Y") if credit_unix else "?"
        except Exception as E:
            logger.warning(f"Cannot compute deferred credit ({str(E)}) for credit '{wallet_credit}'")
            continue
        if credit_unix is None:
            logger.warning(f"Deferred credit slot period missing for credit '{wallet_credit}'")
            continue
        # Strikethrough si crédit expiré
        if credit_unix < now_unix:
            deferred_credits_html.append(
                f"⦙ … <s>{credit_date}: {credit_amount:,} MAS</s>\n"
            )
        else:
            deferred_credits_html.append(
                f"⦙ … {credit_date}: {credit_amount:,} MAS\n"
            )

    short_addr = await get_short_address(wallet_address)
    msg = (
        f"👛 Wallet: <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a>\n"
        + "".join(deferred_credits_html)
        + "\n☝️ Info collected from <a href=\"https://github.com/Massa-Foundation\">MASSA repository</a>"
    )
    return True, msg

@router.message(StateFilter(None), Command("view_credits"))
@logger.catch
async def cmd_view_credits(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_view_credits")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    message_list = message.text.split()
    # Si l'adresse AU... est donnée directement
    if len(message_list) >= 2 and message_list[1].startswith("AU"):
        wallet_address = message_list[1]
        r, msg = await get_credits(wallet_address=wallet_address)
        try:
            await message.reply(
                text=msg,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec'],
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Could not send message: {e}")
        await state.clear()
        return

    # Sinon, menu interactif
    if len(app_globals.app_results) == 0:
        msg = "⭕ Node list is empty\n\n👉 Use the command menu to add a node."
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard()
        )
        await state.clear()
        return

    text = "❓ Tap the node to select or /cancel to quit the scenario:"
    try:
        await state.set_state(CreditsViewer.waiting_node_name)
        await message.reply(
            text=text,
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec'],
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Could not send message: {e}")
        await state.clear()

@router.message(CreditsViewer.waiting_node_name, F.text)
@logger.catch
async def select_wallet_node(message: Message, state: FSMContext) -> None:
    logger.debug("-> select_wallet_node")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text.strip()
    if node_name not in app_globals.app_results:
        msg = (
            f"‼️ Error: Unknown node \"{node_name}\"\n\n"
            "👉 Try /view_credits to view another node or use the command menu for help"
        )
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard()
        )
        await state.clear()
        return

    if len(app_globals.app_results[node_name]['wallets']) == 0:
        msg = (
            f"⭕ No wallets attached to node {node_name}\n\n"
            "👉 Try /add_wallet to add a wallet to this node or use the command menu for help"
        )
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard()
        )
        await state.clear()
        return

    text = "❓ Tap the wallet to select or /cancel to quit the scenario:"
    try:
        await state.set_state(CreditsViewer.waiting_wallet_address)
        await state.set_data(data={"node_name": node_name})
        await message.reply(
            text=text,
            parse_mode="HTML",
            reply_markup=kb_wallets(node_name=node_name),
            request_timeout=app_config['telegram']['sending_timeout_sec'],
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Could not send message: {e}")
        await state.clear()

@router.message(CreditsViewer.waiting_wallet_address, F.text.startswith("AU"))
@logger.catch
async def show_credits_selected(message: Message, state: FSMContext) -> None:
    logger.debug("-> show_credits_selected")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    try:
        user_state = await state.get_data()
        node_name = user_state["node_name"]
        wallet_address = message.text.strip()
    except Exception as e:
        logger.error(f"Cannot read state: {e}")
        await state.clear()
        return

    if wallet_address not in app_globals.app_results[node_name]['wallets']:
        msg = (
            f"‼️ Error: Wallet {wallet_address} is not attached to node \"{node_name}\"\n"
            "👉 Try /view_credits to view another wallet or use the command menu for help"
        )
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard()
        )
        await state.clear()
        return

    r, msg = await get_credits(wallet_address=wallet_address)
    try:
        await message.reply(
            text=msg,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec'],
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Could not send message: {e}")

    await state.clear()
