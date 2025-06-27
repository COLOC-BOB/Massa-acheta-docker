from loguru import logger
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from quickchart import QuickChart
import requests
from aiogram.types import BufferedInputFile

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

        cycles, balances, rolls, total_rolls, ok_blocks, nok_blocks = [], [], [], [], [], []
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
        cycle_min, cycle_max = min(cycles), max(cycles)
        all_cycles = list(range(cycle_min, cycle_max + 1))
        idx_map = {c: i for i, c in enumerate(cycles)}

        def fill(data):
            return [data[idx_map[c]] if c in idx_map else 0 for c in all_cycles]

        # -------- Staking Chart --------
        staking_chart_config = {
            "type": "line",
            "data": {
                "labels": [str(c) for c in all_cycles],
                "datasets": [
                    {
                        "label": "Rolls staked",
                        "yAxisID": "rolls",
                        "borderColor": "Teal",
                        "fill": False,
                        "data": fill(rolls)
                    },
                    {
                        "label": "Final balance",
                        "yAxisID": "balance",
                        "borderColor": "FireBrick",
                        "fill": False,
                        "data": fill(balances)
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
                        {"id": "rolls", "position": "left", "ticks": {"fontColor": "Teal"}},
                        {"id": "balance", "position": "right", "ticks": {"fontColor": "FireBrick"}}
                    ]
                }
            }
        }

        def download_chart_image(url: str) -> bytes:
            resp = requests.get(url)
            if resp.ok:
                return resp.content
            raise Exception(f"QuickChart error {resp.status_code}: {resp.text}")

        # Générer, télécharger et envoyer le staking chart
        staking_chart = QuickChart()
        staking_chart.device_pixel_ratio = 2.0
        staking_chart.width = 600
        staking_chart.height = 300
        staking_chart.config = staking_chart_config
        staking_chart_url = staking_chart.get_url()
        staking_img_bytes = download_chart_image(staking_chart_url)
        caption_staking = (
            f"Cycles collected: {len(all_cycles):,}\n"
            f"Current balance: {balances[-1] if balances else 0:,} MAS\n"
            f"Number of rolls: {rolls[-1] if rolls else 0:,}\n"
            f"Wallet: <code>{short_addr}</code>"
        )
        await message.answer_photo(
            photo=BufferedInputFile(staking_img_bytes, filename="staking_chart.png"),
            caption=caption_staking,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )

        # -------- Blocks Chart --------
        ok_blocks_filled = fill(ok_blocks)
        nok_blocks_filled = fill(nok_blocks)
        est_rewards_per_day_filled = fill(est_rewards_per_day)
        est_blocks_per_cycle_filled = fill(est_blocks_per_cycle)

        blocks_chart_config = {
            "type": "bar",
            "data": {
                "labels": [str(c) for c in all_cycles],
                "datasets": [
                    {
                        "label": "OK blocks",
                        "yAxisID": "blocks",
                        "backgroundColor": "LightSeaGreen",
                        "data": fill(ok_blocks)
                    },
                    {
                        "label": "nOK blocks",
                        "yAxisID": "blocks",
                        "backgroundColor": "LightSalmon",
                        "data": fill(nok_blocks)
                    },
                    {
                        "type": "line",
                        "label": "Est. MAS / Day",
                        "yAxisID": "earnings",
                        "borderColor": "DarkViolet",
                        "fill": False,
                        "data": fill(est_rewards_per_day)
                    },
                    {
                        "type": "line",
                        "label": "Est. Blocks / Cycle",
                        "yAxisID": "blocks",
                        "borderColor": "gray",
                        "fill": False,
                        "data": fill(est_blocks_per_cycle)
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
                        {"id": "blocks", "position": "left", "stacked": True, "ticks": {"fontColor": "LightSeaGreen"}},
                        {"id": "earnings", "position": "right", "ticks": {"fontColor": "DarkViolet"}}
                    ],
                    "xAxes": [
                        {"stacked": True}
                    ]
                }
            }
        }

        blocks_chart = QuickChart()
        blocks_chart.device_pixel_ratio = 2.0
        blocks_chart.width = 600
        blocks_chart.height = 300
        blocks_chart.config = blocks_chart_config
        blocks_chart_url = blocks_chart.get_url()
        blocks_img_bytes = download_chart_image(blocks_chart_url)
        caption_blocks = (
            f"Cycles collected: {len(all_cycles):,}\n"
            f"Operated blocks: {sum(ok_blocks_filled)+sum(nok_blocks_filled):,}\n"
            f"Estimated Blocks / Cycle: {round(sum(est_blocks_per_cycle_filled)/len(est_blocks_per_cycle_filled), 2) if est_blocks_per_cycle_filled else 0}\n"
            f"Estimated Rewards / Cycle: {round(sum(est_rewards_per_day_filled)/len(est_rewards_per_day_filled), 2) if est_rewards_per_day_filled else 0}\n"
            f"Wallet: <code>{short_addr}</code>"
        )
        await message.answer_photo(
            photo=BufferedInputFile(blocks_img_bytes, filename="blocks_chart.png"),
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
