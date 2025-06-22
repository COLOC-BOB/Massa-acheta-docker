from loguru import logger
from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from app_config import app_config
import app_globals
from quickchart import QuickChart
from telegram.menu_utils import build_menu_keyboard

router = Router()

@router.message(StateFilter(None), Command("massa_chart"))
@logger.catch
async def cmd_massa_chart(message: Message, state: FSMContext) -> None:
    logger.debug("-> cmd_massa_chart")
    if message.chat.id != app_globals.ACHETA_CHAT:
        return

    try:
        # --- Préparation des données ---
        massa_stat_keytime_unsorted = {}
        for measure in app_globals.massa_network.get("stat", {}):
            measure_time = measure.get("time", 0)
            measure_cycle = measure.get("cycle", 0)
            measure_stakers = measure.get("stakers", 0)
            measure_rolls = measure.get("rolls", 0)
            massa_stat_keytime_unsorted[measure_time] = {
                "cycle": measure_cycle,
                "stakers": measure_stakers,
                "rolls": measure_rolls
            }

        massa_stat_keytime_sorted = dict(sorted(massa_stat_keytime_unsorted.items()))
        massa_stat_keycycle_unsorted = {}
        for measure in massa_stat_keytime_sorted:
            measure_cycle = massa_stat_keytime_sorted[measure].get("cycle", 0)
            measure_stakers = massa_stat_keytime_sorted[measure].get("stakers", 0)
            measure_rolls = massa_stat_keytime_sorted[measure].get("rolls", 0)
            massa_stat_keycycle_unsorted[measure_cycle] = {
                "stakers": measure_stakers,
                "rolls": measure_rolls
            }

        massa_stat_keycycle_sorted = dict(sorted(massa_stat_keycycle_unsorted.items()))
        total_cycles = len(massa_stat_keycycle_sorted)
        delta_stakers, delta_rolls = 0, 0
        last_stakers, last_rolls = 0, 0

        chart_labels = []
        stakers_list = []
        rolls_list = []

        for cycle in massa_stat_keycycle_sorted:
            stakers = massa_stat_keycycle_sorted[cycle].get("stakers", 0)
            if last_stakers == 0:
                last_stakers = stakers
            delta_stakers += stakers - last_stakers
            last_stakers = stakers

            rolls = massa_stat_keycycle_sorted[cycle].get("rolls", 0)
            if last_rolls == 0:
                last_rolls = rolls
            delta_rolls += rolls - last_rolls
            last_rolls = rolls

            chart_labels.append(str(cycle))  # To ensure label is a string
            stakers_list.append(stakers)
            rolls_list.append(rolls)

        # --- Gestion du bug de rendu si 1 seul point ---
        if len(chart_labels) < 2:
            chart_config = {
                "type": "bar",
                "options": {
                    "title": {
                        "display": True,
                        "text": "MASSA Mainnet chart (single value)" if len(chart_labels) == 1 else "MASSA Mainnet chart"
                    }
                },
                "data": {
                    "labels": chart_labels,
                    "datasets": [
                        {
                            "label": "Active stakers",
                            "backgroundColor": "Teal",
                            "data": stakers_list
                        },
                        {
                            "label": "Rolls staked",
                            "backgroundColor": "FireBrick",
                            "data": rolls_list
                        }
                    ]
                }
            }
        else:
            chart_config = {
                "type": "line",
                "options": {
                    "title": {
                        "display": True,
                        "text": "MASSA Mainnet chart"
                    },
                    "scales": {
                        "yAxes": [
                            {
                                "id": "stakers",
                                "display": True,
                                "position": "left",
                                "ticks": {"fontColor": "Teal"},
                                "gridLines": {"drawOnChartArea": False}
                            },
                            {
                                "id": "rolls",
                                "display": True,
                                "position": "right",
                                "ticks": {"fontColor": "FireBrick"},
                                "gridLines": {"drawOnChartArea": True}
                            }
                        ]
                    }
                },
                "data": {
                    "labels": chart_labels,
                    "datasets": [
                        {
                            "label": "Active stakers",
                            "yAxisID": "stakers",
                            "lineTension": 0.4,
                            "fill": False,
                            "borderColor": "Teal",
                            "borderWidth": 2,
                            "pointRadius": 2,
                            "data": stakers_list
                        },
                        {
                            "label": "Rolls staked",
                            "yAxisID": "rolls",
                            "lineTension": 0.4,
                            "fill": False,
                            "borderColor": "FireBrick",
                            "borderWidth": 2,
                            "pointRadius": 2,
                            "data": rolls_list
                        }
                    ]
                }
            }

        # Format +/-, comme avant
        if delta_stakers > 0:
            delta_stakers_str = f"+{delta_stakers:,}"
        else:
            delta_stakers_str = f"{delta_stakers:,}"
        if delta_rolls > 0:
            delta_rolls_str = f"+{delta_rolls:,}"
        else:
            delta_rolls_str = f"{delta_rolls:,}"

        caption_massa = (
            f"Cycles collected: {total_cycles:,}\n"
            f"Total stakers: {stakers_list[-1] if stakers_list else 0:,} (d: {delta_stakers_str})\n"
            f"Total staked rolls: {rolls_list[-1] if rolls_list else 0:,} (d: {delta_rolls_str})\n"
            f"{'⚠️ Not enough data for a curve.' if len(chart_labels) < 2 else ''}"
        )

        chart = QuickChart()
        chart.device_pixel_ratio = 2.0
        chart.width = 600
        chart.height = 300
        chart.config = chart_config
        chart_url = chart.get_url()

        await message.answer_photo(
            photo=chart_url,
            caption=caption_massa,
            parse_mode="HTML",
            reply_markup=build_menu_keyboard(),
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
    except Exception as E:
        logger.error(f"Cannot prepare MASSA Mainnet chart ({str(E)})")
        await message.reply(
            text="🤷 Charts are temporarily unavailable. Try later.\n☝ Use the command menu to learn bot commands",
            reply_markup=build_menu_keyboard(),
            parse_mode="HTML",
            request_timeout=app_config['telegram']['sending_timeout_sec']
        )
