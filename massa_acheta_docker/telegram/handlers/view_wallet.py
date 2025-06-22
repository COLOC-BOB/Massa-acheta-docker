# massa_acheta_docker/telegram/handlers/view_wallet.py
from loguru import logger
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app_config import app_config
import app_globals

from telegram.keyboards.kb_nodes import kb_nodes
from telegram.keyboards.kb_wallets import kb_wallets
from telegram.menu_utils import build_menu_keyboard
from remotes_utils import get_short_address, get_last_seen, get_rewards_mas_day

class WalletViewer(StatesGroup):
    waiting_node_name = State()
    waiting_wallet_address = State()

router = Router()

async def safe_reply(message, text, **kwargs):
    # kwargs: parse_mode, reply_markup, request_timeout, disable_web_page_preview...
    if hasattr(message, "reply") and callable(message.reply):
        await message.reply(text=text, **kwargs)
    else:
        from aiogram import Bot
        bot: Bot = app_globals.tg_bot
        chat_id = getattr(message, "chat", None)
        if hasattr(chat_id, "id"):
            chat_id = chat_id.id
        elif hasattr(message, "chat_id"):
            chat_id = message.chat_id
        else:
            chat_id = app_globals.ACHETA_CHAT
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)

@router.message(StateFilter(None), Command("view_wallet"))
@logger.catch
async def cmd_view_wallet(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_view_wallet")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    nodes = list(app_globals.app_results.keys())
    if len(nodes) == 0:
        text = (
            "⭕ Node list is empty\n\n"
            "👉 Use the command menu to learn how to add a node to bot"
        )
        try:
            await safe_reply(
                message,
                text=text,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
                
            )
        except Exception as e:
            logger.error(f"Could not send message: {e}")
        await state.clear()
        return

    # Cas unique node
    if len(nodes) == 1:
        node_name = nodes[0]
        wallets = list(app_globals.app_results[node_name]['wallets'].keys())
        if len(wallets) == 0:
            text = (
                f"⭕ No wallets attached to node {node_name}\n\n"
                "👉 Try /add_wallet to add wallet to the node or use the command menu for help"
            )
            try:
                await safe_reply(
                    message,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=build_menu_keyboard(),
                    request_timeout=app_config['telegram']['sending_timeout_sec']
                )
            except Exception as e:
                logger.error(f"Could not send message: {e}")
            await state.clear()
            return

        # Cas unique wallet : on affiche direct
        if len(wallets) == 1:
            await state.set_data(data={"node_name": node_name})
            # Appelle show_wallet directement, mais avec un vrai message Telegram : on modifie son text
            class DummyMsg:
                def __init__(self, wallet_address, chat):
                    self.text = wallet_address
                    self.chat = chat
                    self.chat_id = chat.id if hasattr(chat, "id") else chat
            fake_msg = DummyMsg(wallets[0], message.chat)
            await show_wallet(fake_msg, state)
            return

        # Sinon: bouton wallet
        text = "❓ Tap the wallet to select or /cancel to quit the scenario:"
        try:
            await state.set_state(WalletViewer.waiting_wallet_address)
            await state.set_data(data={"node_name": node_name})
            await safe_reply(
                message,
                text=text,
                parse_mode="HTML",
                reply_markup=kb_wallets(node_name=node_name),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as e:
            logger.error(f"Could not send message: {e}")
            await state.clear()
        return

    # Cas classique: plusieurs nodes -> bouton node
    text = "❓ Tap the node to select or /cancel to quit the scenario"
    try:
        await state.set_state(WalletViewer.waiting_node_name)
        await safe_reply(
            message,
            text=text,
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"Could not send message: {e}")
        await state.clear()
    return

@router.message(WalletViewer.waiting_node_name, F.text)
@logger.catch
async def select_wallet_to_show(message: Message, state: FSMContext) -> None:
    logger.debug("-> select_wallet_to_show")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text
    if node_name not in app_globals.app_results:
        text = (
            f"‼️ Error: Unknown node \"{node_name}\"\n\n"
            "👉 Try /view_wallet to view another wallet or use the command menu for help"
        )
        try:
            await safe_reply(
                message,
                text=text,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as e:
            logger.error(f"Could not send message: {e}")
        await state.clear()
        return

    if len(app_globals.app_results[node_name]['wallets']) == 0:
        text = (
            f"⭕ No wallets attached to node {node_name}\n\n"
            "👉 Try /add_wallet to add wallet to the node or use the command menu for help"
        )
        try:
            await safe_reply(
                message,
                text=text,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as e:
            logger.error(f"Could not send message: {e}")
        await state.clear()
        return

    text = "❓ Tap the wallet to select or /cancel to quit the scenario:"
    try:
        await state.set_state(WalletViewer.waiting_wallet_address)
        await state.set_data(data={"node_name": node_name})
        await safe_reply(
            message,
            text=text,
            parse_mode="HTML",
            reply_markup=kb_wallets(node_name=node_name),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"Could not send message: {e}")
        await state.clear()
    return

@router.message(WalletViewer.waiting_wallet_address, F.text.startswith("AU"))
@logger.catch
async def show_wallet(message: Message, state: FSMContext) -> None:
    logger.debug("-> show_wallet")
    if getattr(message, "chat", None) and hasattr(message.chat, "id"):
        chat_id = message.chat.id
    elif hasattr(message, "chat_id"):
        chat_id = message.chat_id
    else:
        chat_id = app_globals.ACHETA_CHAT
    if chat_id != app_globals.ACHETA_CHAT:
        return

    try:
        user_state = await state.get_data()
        node_name = user_state['node_name']
        wallet_address = message.text
    except Exception as e:
        logger.error(f"Cannot read state: {e}")
        await state.clear()
        return

    if wallet_address not in app_globals.app_results[node_name]['wallets']:
        short_addr = await get_short_address(wallet_address)
        text = (
            f"‼️ Error: Wallet <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a> is not attached to node \"{node_name}\"\n"
            "👉 Try /view_wallet to view another wallet or use the command menu for help"
        )
        try:
            await safe_reply(
                message,
                text=text,
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
        except Exception as e:
            logger.error(f"Could not send message: {e}")
        await state.clear()
        return

    w_data = app_globals.app_results[node_name]['wallets'][wallet_address]
    wallet_last_seen = await get_last_seen(last_time=w_data['last_update'])
    node_last_seen = await get_last_seen(last_time=app_globals.app_results[node_name]['last_update'])
    node_status = (
        f"🌿 Status: Online (last seen: {node_last_seen})"
        if app_globals.app_results[node_name]['last_status'] == True
        else f"☠️ Status: Offline (last seen: {node_last_seen})"
    )

    if w_data['last_status'] != True:
        short_addr = await get_short_address(wallet_address)
        text = (
            f"🏠 <b>Node:</b> {node_name}\n"
            f"📍 <code>{app_globals.app_results[node_name]['url']}</code>\n"
            f"{node_status}\n"
            f"⁉️ No actual data for wallet: <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a>\n"
            f"👁 Last successful info update: {wallet_last_seen}\n"
            f"💻 <b>Result:</b> <code>{str(w_data['last_result'])}</code>\n"
            f"⚠️ Check wallet address or node settings!\n"
            f"☝️ Service checks updates: every {app_config['service']['main_loop_period_min']} minutes\n"
        )
    else:
        wallet_final_balance = w_data['final_balance']
        wallet_candidate_rolls = w_data['candidate_rolls']
        wallet_active_rolls = w_data['active_rolls']
        wallet_missed_blocks = w_data['missed_blocks']
        wallet_produced_blocks = w_data.get('produced_blocks', 0)
        wallet_computed_rewards = await get_rewards_mas_day(rolls_number=wallet_active_rolls)
        wallet_thread = w_data['last_result'].get("thread", 0)
        short_addr = await get_short_address(wallet_address)
        cycles_html = ""
        wallet_cycles = w_data['last_result'].get("cycle_infos", [])
        if len(wallet_cycles) == 0:
            cycles_html += "🌀 Cycles info: No data\n"
        else:
            cycles_html += "🌀 Cycles info (Produced / Missed):\n"
            for wallet_cycle in wallet_cycles:
                cycle_num = wallet_cycle.get("cycle", 0)
                ok_count = wallet_cycle.get("ok_count", 0)
                nok_count = wallet_cycle.get("nok_count", 0)
                cycles_html += f"&nbsp;&nbsp;⋅ Cycle {cycle_num}: ( {ok_count} / {nok_count} )\n"

        logger.debug(f"last_result content: {w_data['last_result']}")
        wallet_credits = w_data['last_result'].get("deferred_credits", [])
        if not wallet_credits:
            credits_html = "💳 Deferred credits: No data\n"
        else:
            credits_html = "💳 Deferred credits:\n"
            for wallet_credit in wallet_credits:
                try:
                    credit_amount = float(wallet_credit.get('amount', 0) or 0)
                    credit_slot = wallet_credit.get('slot')
                    if not isinstance(credit_slot, dict) or 'period' not in credit_slot:
                        logger.warning(f"Deferred credit slot/period missing for credit '{wallet_credit}'")
                        continue

                    credit_period = credit_slot['period']
                    try:
                        period_int = int(credit_period)
                    except Exception as e:
                        logger.warning(f"Invalid period '{credit_period}' in deferred credit: {e}")
                        continue

                    credit_unix = 1705312800 + (period_int * 16)
                    credit_date = datetime.utcfromtimestamp(credit_unix).strftime("%b %d, %Y")

                    credits_html += f"  ⋅ {credit_date}: {credit_amount:,.4f} MAS\n"

                except Exception as e:
                    logger.warning(f"Cannot compute deferred credit: {e} for credit '{wallet_credit}'")
                    continue

        text = (
            f"🏠 <b>Node:</b> {node_name}\n"
            f"📍 <code>{app_globals.app_results[node_name]['url']}</code>\n"
            f"{node_status}\n"
            f"👛 Wallet: <a href=\"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}\">{short_addr}</a>\n"
            f"👁 Info updated: {wallet_last_seen}\n"
            f"💰 Final balance: {wallet_final_balance:,} MAS\n"
            f"🗞 Candidate / Active rolls: {wallet_candidate_rolls:,} / {wallet_active_rolls:,}\n"
            f"🥊 Missed blocks: {wallet_missed_blocks}\n"
            f"🥊 Produced blocks: {wallet_produced_blocks}\n"
            f"🪙 Estimated earnings ≈ {wallet_computed_rewards:,} MAS / Day\n"
            f"🔎 Detailed info:\n"
            f"🧵 Thread: {wallet_thread}\n"
            f"{cycles_html}"
            f"{credits_html}"
            f"☝️ Service checks updates: every {app_config['service']['main_loop_period_min']} minutes"
        )

    try:
        await safe_reply(
            message,
            text=text,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            disable_web_page_preview=True,
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as e:
        logger.error(f"Could not send message: {e}")

    await state.clear()
    return
