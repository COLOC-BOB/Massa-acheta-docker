import asyncio
import json
import os
import time
from datetime import datetime
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert

WATCH_FILE = "watchers_state/missed_blocks_seen.json"

def load_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Could not load missed blocks history: {e}")
    return {}

def save_history(history):
    with open(WATCH_FILE, "wt") as f:
        json.dump(history, f, indent=2)

async def watch_missed_blocks(polling_interval=30):
    logger.info("Watcher: missed_blocks started")
    history = load_history()

    while True:
        for node_name, node_data in app_globals.app_results.items():
            for wallet_address in node_data.get("wallets", {}):
                # Appel API pour obtenir infos du wallet
                try:
                    resp = await pull_http_api(
                        api_url=node_data['url'],
                        api_method="POST",
                        api_payload=json.dumps({
                            "jsonrpc": "2.0",
                            "method": "get_addresses",
                            "params": [[wallet_address]],
                            "id": 0
                        }),
                        api_content_type="application/json"
                    )
                    result = resp.get("result")
                    if not result or not isinstance(result, list):
                        continue
                    cycle_infos = result[0].get("cycle_infos", [])
                except Exception as e:
                    logger.error(f"Error fetching wallet {wallet_address}: {e}")
                    continue

                # Parcours chaque cycle du wallet pour détecter des blocks manqués
                for cycle in cycle_infos:
                    cycle_num = cycle.get("cycle")
                    missed = cycle.get("nok_count", 0)
                    if missed and missed > 0:
                        # Clef unique : wallet + cycle + nombre manqués
                        key = f"{wallet_address}:{cycle_num}:{missed}"
                        if key not in history:
                            dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            history[key] = {
                                "wallet": wallet_address,
                                "node": node_name,
                                "cycle": cycle_num,
                                "missed": missed,
                                "detected_at": int(time.time()),
                                "datetime": dt
                            }
                            save_history(history)
                            message = (
                                f"❌ <b>Bloc manqué détecté</b>\n"
                                f"👛 Wallet: <code>{wallet_address}</code>\n"
                                f"🏠 Node: <b>{node_name}</b>\n"
                                f"🌀 Cycle: <b>{cycle_num}</b>\n"
                                f"⛔ Total manqués ce cycle: <b>{missed}</b>\n"
                                f"🕒 {dt}\n"
                                f"🗂 Ajouté à l'historique."
                            )
                            await send_alert(
                                alert_type="wallet_block_miss",
                                node=node_name,
                                wallet=wallet_address,
                                level="warning",
                                html=message
                            )
                            logger.warning(f"[MISSED_BLOCK] New missed block: {key} ({dt})")

        await asyncio.sleep(polling_interval)
