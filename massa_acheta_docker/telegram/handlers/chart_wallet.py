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
    logger.debug(f"[CHART_WALLET]  -> cmd_chart_wallet")
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
    logger.debug(f"[CHART_WALLET] -> select_wallet_to_show")
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
    logger.debug(f"[CHART_WALLET] -> show_wallet")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    try:
        user_state = await state.get_data()
        node_name = user_state['node_name']
        wallet_address = message.text.strip()
    except Exception as e:
        logger.error(f"[CHART_WALLET] Cannot read state: {e}")
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

        # Extraction brut
        cycles = []
        balances, rolls, total_rolls, ok_blocks, nok_blocks = [], [], [], [], []
        est_rewards_per_day, est_blocks_per_cycle = [], []
        for measure in stats:
            cycles.append(int(measure.get("cycle", 0)))
            balances.append(measure.get("balance", 0))
            rolls.append(measure.get("rolls", 0))
            total_rolls.append(measure.get("total_rolls", 0))
            ok_blocks.append(measure.get("ok_blocks", 0))
            nok_blocks.append(measure.get("nok_blocks", 0))
            est_rewards_per_day.append(await get_rewards_mas_day(measure.get("rolls", 0), measure.get("total_rolls", 0)))
            est_blocks_per_cycle.append(await get_rewards_blocks_cycle(measure.get("rolls", 0), measure.get("total_rolls", 0)))

        logger.debug(f"cycles={cycles}")

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

        # --- ALIGNEMENT X LINÉAIRE ---
        cycle_min, cycle_max = min(cycles), max(cycles)
        all_cycles = list(range(cycle_min, cycle_max + 1))

        # Map cycle → index
        idx_map = {c: i for i, c in enumerate(cycles)}

        def fill(data):
            # Remplit avec 0 ou None si absent
            return [data[idx_map[c]] if c in idx_map else 0 for c in all_cycles]

        # Séries Y linéaires
        balances_filled = fill(balances)
        rolls_filled = fill(rolls)
        ok_blocks_filled = fill(ok_blocks)
        nok_blocks_filled = fill(nok_blocks)
        est_rewards_per_day_filled = fill(est_rewards_per_day)
        est_blocks_per_cycle_filled = fill(est_blocks_per_cycle)

        # Pour Chart.js mode "x/y"
        ok_blocks_points = [{"x": c, "y": ok_blocks_filled[i]} for i, c in enumerate(all_cycles)]
        nok_blocks_points = [{"x": c, "y": nok_blocks_filled[i]} for i, c in enumerate(all_cycles)]
        est_rewards_points = [{"x": c, "y": est_rewards_per_day_filled[i]} for i, c in enumerate(all_cycles)]
        est_blocks_cycle_points = [{"x": c, "y": est_blocks_per_cycle_filled[i]} for i, c in enumerate(all_cycles)]

        # ---- Chart "blocks" avec axe linéaire (plus de category) ----
        blocks_chart_config = {
            "type": "bar",
            "data": {
                "datasets": [
                    {
                        "type": "line",
                        "label": "Est. MAS / Day",
                        "yAxisID": "earnings",
                        "lineTension": 0.3,
                        "fill": True,
                        "backgroundColor": "rgba(150,0,255,0.1)",
                        "borderColor": "DarkViolet",
                        "borderWidth": 2,
                        "pointRadius": 1,
                        "data": est_rewards_points,
                        "order": 1
                    },
                    {
                        "type": "bar",
                        "label": "OK blocks",
                        "yAxisID": "blocks",
                        "backgroundColor": "rgba(50,200,150,0.7)",
                        "data": ok_blocks_points,
                        "categoryPercentage": 0.7,
                        "barPercentage": 0.8,
                        "order": 2
                    },
                    {
                        "type": "bar",
                        "label": "nOK blocks",
                        "yAxisID": "blocks",
                        "backgroundColor": "rgba(250,150,100,0.5)",
                        "data": nok_blocks_points,
                        "categoryPercentage": 0.7,
                        "barPercentage": 0.8,
                        "order": 2
                    },
                    {
                        "type": "line",
                        "label": "Est. Blocks / Cycle",
                        "yAxisID": "blocks",
                        "lineTension": 0.3,
                        "fill": False,
                        "borderColor": "gray",
                        "borderWidth": 1,
                        "pointRadius": 0,
                        "data": est_blocks_cycle_points,
                        "order": 0
                    }
                ]
            },
            "options": {
                "title": {
                    "display": True,
                    "text": f"Wallet: {short_addr}"
                },
                "scales": {
                    "xAxes": [{
                        "type": "linear",
                        "position": "bottom",
                        "ticks": {
                            "min": cycle_min,
                            "max": cycle_max,
                            "stepSize": 1,
                            "fontSize": 10,
                            "callback": "function(value,index,values){ return Math.round(value); }",
                            "autoSkip": True,
                            "maxTicksLimit": 15
                        },
                        "scaleLabel": {
                            "display": True,
                            "labelString": "Cycle"
                        }
                    }],
                    "yAxes": [
                        {
                            "id": "blocks",
                            "display": True,
                            "position": "left",
                            "stacked": True,
                            "ticks": {"min": 0, "fontColor": "#228877"},
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
                    ]
                },
                "legend": {
                    "labels": {
                        "fontSize": 12
                    }
                },
                "tooltips": {
                    "mode": "index",
                    "intersect": False
                }
            }
        }

        # Pour le staking_chart, tu peux garder l'ancien code si tu veux du "category",
        # ou faire la même chose (axe linéaire) si besoin !

        staking_chart_config = {
            "type": "line",
            "data": {
                "labels": [str(c) for c in all_cycles],
                "datasets": [
                    {
                        "label": "Rolls staked",
                        "yAxisID": "rolls",
                        "lineTension": 0.4,
                        "fill": False,
                        "borderColor": "Teal",
                        "borderWidth": 2,
                        "pointRadius": 2,
                        "data": rolls_filled
                    },
                    {
                        "label": "Final balance",
                        "yAxisID": "balance",
                        "lineTension": 0.4,
                        "fill": False,
                        "borderColor": "FireBrick",
                        "borderWidth": 2,
                        "pointRadius": 2,
                        "data": balances_filled
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
            f"Cycles collected: {len(all_cycles):,}\n"
            f"Current balance: {balances_filled[-1] if balances_filled else 0:,} MAS\n"
            f"Number of rolls: {rolls_filled[-1] if rolls_filled else 0:,}\n"
            f"{'⚠️ Not enough data for a curve.' if len(all_cycles) < 2 else ''}\n"
            f"Wallet: <code>{short_addr}</code>"
        )
        caption_blocks = (
            f"Cycles collected: {len(all_cycles):,}\n"
            f"Operated blocks: {sum(ok_blocks_filled)+sum(nok_blocks_filled):,}\n"
            f"Estimated Blocks / Cycle: {round(sum(est_blocks_per_cycle_filled)/len(est_blocks_per_cycle_filled), 2) if est_blocks_per_cycle_filled else 0}\n"
            f"Estimated Rewards / Cycle: {round(sum(est_rewards_per_day_filled)/len(est_rewards_per_day_filled), 2) if est_rewards_per_day_filled else 0}\n"
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
        logger.error(f"[CHART_WALLET] Cannot prepare wallet chart ({str(E)})")
        await message.reply(
            text="🤷 Charts are temporarily unavailable. Try later.\n☝ Use the command menu to learn bot commands",
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    await state.clear()
