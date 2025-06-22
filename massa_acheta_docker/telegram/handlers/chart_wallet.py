# massa_acheta_docker/telegram/handlers/chart_wallet.py
from loguru import logger
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from quickchart import QuickChart

from app_config import app_config
import app_globals

from telegram.keyboards.kb_nodes import kb_nodes
from telegram.keyboards.kb_wallets import kb_wallets
from remotes_utils import get_short_address, get_rewards_mas_day, get_rewards_blocks_cycle
from telegram.menu_utils import build_menu_keyboard

class ChartWalletViewer(StatesGroup):
    waiting_node_name = State()
    waiting_wallet_address = State()

router = Router()

@router.message(Command("chart_wallet"))
@logger.catch
async def cmd_chart_wallet(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_chart_wallet")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    if len(app_globals.app_results) == 0:
        await message.reply(
            text="⭕ Node list is empty\n\n👉 Use the command menu to learn how to add a node to bot",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    # Si un seul node, saute la sélection
    if len(app_globals.app_results) == 1:
        node_name = next(iter(app_globals.app_results))
        await select_wallet_interactive(message, state, node_name)
        return

    await state.set_state(ChartWalletViewer.waiting_node_name)
    await message.reply(
        text="❓ Tap the node to select or /cancel to quit the scenario",
        parse_mode="HTML",
        reply_markup=kb_nodes(),
        request_timeout=app_config['telegram']['sending_timeout_sec']
    )

@router.message(ChartWalletViewer.waiting_node_name, F.text)
@logger.catch
async def select_wallet_to_show(message: Message, state: FSMContext) -> None:
    logger.debug("-> select_wallet_to_show")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    node_name = message.text.strip()
    await select_wallet_interactive(message, state, node_name)

async def select_wallet_interactive(message: Message, state: FSMContext, node_name: str):
    if node_name not in app_globals.app_results:
        await message.reply(
            text=f"‼️ <b>Error:</b> Unknown node \"{node_name}\"\n\n👉 Try again.",
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    wallets = app_globals.app_results[node_name]['wallets']
    if len(wallets) == 0:
        await message.reply(
            text=f"⭕ No wallets attached to node {node_name}\n\n👉 Attach a wallet first.",
            parse_mode="HTML",
            reply_markup=kb_nodes(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    # Si un seul wallet, saute la sélection
    if len(wallets) == 1:
        wallet_address = next(iter(wallets))
        await show_wallet_chart(message, state, node_name, wallet_address)
        return

    await state.set_state(ChartWalletViewer.waiting_wallet_address)
    await state.set_data(data={"node_name": node_name})
    await message.reply(
        text="❓ Tap the wallet to select or /cancel to quit the scenario:",
        parse_mode="HTML",
        reply_markup=kb_wallets(node_name=node_name),
        request_timeout=app_config['telegram']['sending_timeout_sec']
    )

@router.message(ChartWalletViewer.waiting_wallet_address, F.text.startswith("AU"))
@logger.catch
async def show_wallet(message: Message, state: FSMContext) -> None:
    logger.debug("-> show_wallet")
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

    await show_wallet_chart(message, state, node_name, wallet_address)

async def show_wallet_chart(message: Message, state: FSMContext, node_name: str, wallet_address: str):
    if wallet_address not in app_globals.app_results[node_name]['wallets']:
        short_addr = await get_short_address(wallet_address)
        await message.reply(
            text=f"‼️ <b>Error:</b> Wallet <code>{short_addr}</code> is not attached to node \"{node_name}\"\n👉 Try again.",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await state.clear()
        return

    try:
        stats = app_globals.app_results[node_name]['wallets'][wallet_address].get("stat", {})
        # Extraction des données triées par cycle
        cycles, balances, rolls, total_rolls, ok_blocks, nok_blocks = [], [], [], [], [], []
        est_rewards_per_day, est_blocks_per_cycle = [], []
        for measure in stats:
            cycles.append(str(measure.get("cycle", 0)))
            balances.append(measure.get("balance", 0))
            rolls.append(measure.get("rolls", 0))
            total_rolls.append(measure.get("total_rolls", 0))
            ok_blocks.append(measure.get("ok_blocks", 0))
            nok_blocks.append(measure.get("nok_blocks", 0))
            est_rewards_per_day.append(await get_rewards_mas_day(measure.get("rolls", 0), measure.get("total_rolls", 0)))
            est_blocks_per_cycle.append(await get_rewards_blocks_cycle(measure.get("rolls", 0), measure.get("total_rolls", 0)))

        logger.debug(f"cycles={cycles}")
        logger.debug(f"rolls={rolls}")
        logger.debug(f"balances={balances}")

        if not cycles:
            await message.reply(
                text="⏳ No historical data for this wallet. Wait for the next update.",
                parse_mode="HTML",
                reply_markup=build_menu_keyboard(),
                request_timeout=app_config['telegram']['sending_timeout_sec']
            )
            await state.clear()
            return

        short_addr = await get_short_address(wallet_address)

        # Si 1 seul point, bar chart au lieu de line chart (évite le bug visuel)
        if len(cycles) < 2:
            staking_chart_config = {
                "type": "bar",
                "data": {
                    "labels": cycles,
                    "datasets": [
                        {
                            "label": "Rolls staked",
                            "backgroundColor": "Teal",
                            "data": rolls,
                        },
                        {
                            "label": "Final balance",
                            "backgroundColor": "FireBrick",
                            "data": balances,
                        }
                    ]
                },
                "options": {
                    "title": {
                        "display": True,
                        "text": f"Wallet: {short_addr} (single value)"
                    }
                }
            }
        else:
            staking_chart_config = {
                "type": "line",
                "data": {
                    "labels": cycles,
                    "datasets": [
                        {
                            "label": "Rolls staked",
                            "yAxisID": "rolls",
                            "lineTension": 0.4,
                            "fill": False,
                            "borderColor": "Teal",
                            "borderWidth": 2,
                            "pointRadius": 2,
                            "data": rolls
                        },
                        {
                            "label": "Final balance",
                            "yAxisID": "balance",
                            "lineTension": 0.4,
                            "fill": False,
                            "borderColor": "FireBrick",
                            "borderWidth": 2,
                            "pointRadius": 2,
                            "data": balances
                        }
                    ]
                },
                "options": {
                    "title": {
                        "display": True,
                        "text": f"Wallet: {short_addr}"
                    },
                    "scales": {
                        "yAxes": [
                            {
                                "id": "rolls",
                                "display": True,
                                "position": "left",
                                "ticks": {"fontColor": "Teal"},
                                "gridLines": {"drawOnChartArea": False}
                            },
                            {
                                "id": "balance",
                                "display": True,
                                "position": "right",
                                "ticks": {"fontColor": "FireBrick"},
                                "gridLines": {"drawOnChartArea": True}
                            }
                        ]
                    }
                }
            }

                # ----------- CORRECTIF blocks_chart_config ----------------
        if len(cycles) < 2:
            # Fallback: Simple bar chart si 1 seul point
            blocks_chart_config = {
                "type": "bar",
                "data": {
                    "labels": cycles,
                    "datasets": [
                        {
                            "label": "OK blocks",
                            "backgroundColor": "LightSeaGreen",
                            "data": ok_blocks
                        },
                        {
                            "label": "nOK blocks",
                            "backgroundColor": "LightSalmon",
                            "data": nok_blocks
                        },
                        {
                            "label": "Est. MAS / Day",
                            "backgroundColor": "DarkViolet",
                            "data": est_rewards_per_day
                        },
                        {
                            "label": "Est. Blocks / Cycle",
                            "backgroundColor": "lightgray",
                            "data": est_blocks_per_cycle
                        }
                    ]
                },
                "options": {
                    "title": {
                        "display": True,
                        "text": f"Wallet: {short_addr} (single value)"
                    }
                }
            }
        else:
            # Version normale (multi-points)
            blocks_chart_config = {
                "type": "bar",
                "data": {
                    "labels": cycles,
                    "datasets": [
                        {
                            "type": "line",
                            "label": "Est. MAS / Day",
                            "yAxisID": "earnings",
                            "lineTension": 0.4,
                            "fill": False,
                            "borderColor": "DarkViolet",
                            "borderWidth": 2,
                            "pointRadius": 2,
                            "data": est_rewards_per_day
                        },
                        {
                            "type": "bar",
                            "label": "OK blocks",
                            "yAxisID": "blocks",
                            "backgroundColor": "LightSeaGreen",
                            "data": ok_blocks
                        },
                        {
                            "type": "bar",
                            "label": "nOK blocks",
                            "yAxisID": "blocks",
                            "backgroundColor": "LightSalmon",
                            "data": nok_blocks
                        },
                        {
                            "type": "line",
                            "label": "Est. Blocks / Cycle",
                            "yAxisID": "blocks",
                            "lineTension": 0.4,
                            "fill": True,
                            "borderColor": "lightgray",
                            "backgroundColor": "rgba(220, 220, 220, 0.4)",
                            "borderWidth": 0,
                            "pointRadius": 0,
                            "data": est_blocks_per_cycle
                        }
                    ]
                },
                "options": {
                    "title": {
                        "display": True,
                        "text": f"Wallet: {short_addr}"
                    },
                    "scales": {
                        "yAxes": [
                            {
                                "id": "blocks",
                                "display": True,
                                "position": "left",
                                "stacked": True,
                                "ticks": {"min": 0, "fontColor": "LightSeaGreen"},
                                "gridLines": {"drawOnChartArea": False}
                            },
                            {
                                "id": "earnings",
                                "display": True,
                                "position": "right",
                                "stacked": False,
                                "ticks": {"fontColor": "DarkViolet"},
                                "gridLines": {"drawOnChartArea": True}
                            }
                        ],
                        "xAxes": [{"stacked": True}]
                    }
                }
            }


        # Génération QuickChart
        staking_chart = QuickChart()
        staking_chart.device_pixel_ratio = 2.0
        staking_chart.width = 600
        staking_chart.height = 300
        staking_chart.config = staking_chart_config
        staking_chart_url = staking_chart.get_url()

        blocks_chart = QuickChart()
        blocks_chart.device_pixel_ratio = 2.0
        blocks_chart.width = 600
        blocks_chart.height = 300
        blocks_chart.config = blocks_chart_config
        blocks_chart_url = blocks_chart.get_url()

        caption_staking = (
            f"Cycles collected: {len(cycles):,}\n"
            f"Current balance: {balances[-1] if balances else 0:,} MAS\n"
            f"Number of rolls: {rolls[-1] if rolls else 0:,}\n"
            f"{'⚠️ Not enough data for a curve.' if len(cycles) < 2 else ''}\n"
            f"Wallet: <code>{short_addr}</code>"
        )
        caption_blocks = (
            f"Cycles collected: {len(cycles):,}\n"
            f"Operated blocks: {sum(ok_blocks)+sum(nok_blocks):,}\n"
            f"Estimated Blocks / Cycle: {round(sum(est_blocks_per_cycle)/len(est_blocks_per_cycle), 2) if est_blocks_per_cycle else 0}\n"
            f"Estimated Rewards / Cycle: {round(sum(est_rewards_per_day)/len(est_rewards_per_day), 2) if est_rewards_per_day else 0}\n"
            f"Wallet: <code>{short_addr}</code>"
        )

        await message.answer_photo(
            photo=staking_chart_url,
            caption=caption_staking,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
        await message.answer_photo(
            photo=blocks_chart_url,
            caption=caption_blocks,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )

    except Exception as E:
        logger.error(f"Cannot prepare wallet chart ({str(E)})")
        await message.reply(
            text="🤷 Charts are temporarily unavailable. Try later.\n☝ Use the command menu to learn bot commands",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    await state.clear()

