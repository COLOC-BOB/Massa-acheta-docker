# massa_acheta_docker/watchers/missed_blocks.py

import asyncio
import json
import os
from datetime import datetime
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert
from watchers.watchers_control import is_watcher_enabled

WATCH_FILE = "watchers_state/missed_blocks_seen.json"
_save_lock = asyncio.Lock()

def load_json_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[MISSED_BLOCK] Could not load missed blocks watcher state: {str(e)}")
    return {}

async def save_json_history(history):
    async with _save_lock:
        tmp_file = WATCH_FILE + ".tmp"
        try:
            with open(tmp_file, "wt") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, WATCH_FILE)
        except Exception as e:
            logger.error(f"[MISSED_BLOCK] Could not save missed blocks watcher state: {str(e)}")

async def watch_missed_blocks(polling_interval=30):
    logger.info(f"[MISSED_BLOCK] JSON Watcher started")
    # Structure :
    # {
    #   "My node": {
    #     "AU12xxx...": [
    #         {"datetime": "...", "cycle": ..., "missed": ...},
    #         ...
    #     ],
    #     ...
    #   },
    #   ...
    # }
    history = load_json_history()
    if not isinstance(history, dict):
        history = {}

    while True:
        if not is_watcher_enabled("missed_blocks"):
            logger.info(f"[MISSED_BLOCK] Désactivé, je dors...")
            await asyncio.sleep(60)
            continue

        for node_name, node_data in app_globals.app_results.items():
            wallets = node_data.get("wallets", {})
            if not wallets:
                continue

            if node_name not in history:
                history[node_name] = {}

            for wallet_address in wallets:
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
                    if (
                        not resp or
                        "result" not in resp or
                        "result" not in resp["result"] or
                        not isinstance(resp["result"]["result"], list) or
                        not resp["result"]["result"]
                    ):
                        continue

                    addr_info = resp["result"]["result"][0]
                    cycle_infos = addr_info.get("cycle_infos", [])

                    if wallet_address not in history[node_name]:
                        history[node_name][wallet_address] = []

                    # On récupère les entrées déjà enregistrées (cycle, missed)
                    seen = {(c["cycle"], c["missed"]) for c in history[node_name][wallet_address] if "cycle" in c and "missed" in c}

                    for cycle in cycle_infos:
                        cycle_num = cycle.get("cycle")
                        missed = cycle.get("nok_count", 0)
                        if missed and missed > 0:
                            key_tuple = (cycle_num, missed)
                            if key_tuple not in seen:
                                now_iso = datetime.now().isoformat()
                                entry = {
                                    "datetime": now_iso,
                                    "cycle": cycle_num,
                                    "missed": missed
                                }
                                history[node_name][wallet_address].append(entry)
                                seen.add(key_tuple)

                                message = (
                                    f"❌ <b>Missed block detected</b>\n"
                                    f"👛 Wallet: <code>{wallet_address}</code>\n"
                                    f"🏠 Node: <b>{node_name}</b>\n"
                                    f"🌀 Cycle: <b>{cycle_num}</b>\n"
                                    f"⛔ Total missed this cycle: <b>{missed}</b>\n"
                                    f"🕒 {now_iso}\n"
                                    f"🗂 Added to history."
                                )
                                await send_alert(
                                    alert_type="wallet_block_miss",
                                    node=node_name,
                                    wallet=wallet_address,
                                    level="warning",
                                    html=message
                                )
                                logger.warning(f"[MISSED_BLOCK] New missed block for {wallet_address}@{node_name}: cycle={cycle_num}, missed={missed}")

                except Exception as e:
                    logger.error(f"[MISSED_BLOCK] Error fetching wallet {wallet_address}: {e}")

        await save_json_history(history)
        await asyncio.sleep(polling_interval)
