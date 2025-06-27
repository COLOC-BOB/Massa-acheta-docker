# massa_acheta_docker/watchers/rolls.py

import asyncio
import json
import os
from datetime import datetime
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert
from watchers.watchers_control import is_watcher_enabled

WATCH_FILE = "watchers_state/rolls_seen.json"
MAX_HISTORY = 1000  # nombre de points max par wallet

async def load_json_history():
    if os.path.exists(WATCH_FILE):
        try:
            async with asyncio.Lock():
                with open(WATCH_FILE, "rt") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"[ROLLS] Could not load rolls watcher state: {e}")
    return {}

async def save_json_history(history):
    tmp_file = WATCH_FILE + ".tmp"
    try:
        async with asyncio.Lock():
            with open(tmp_file, "wt", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, WATCH_FILE)
    except Exception as e:
        logger.error(f"[ROLLS] Could not save rolls watcher state: {e}")

async def watch_rolls(polling_interval=30):
    logger.info("[ROLLS] JSON Watcher started")
    history = await load_json_history()
    if not isinstance(history, dict):
        history = {}

    while True:
        if not is_watcher_enabled("rolls"):
            logger.info("[ROLLS] Désactivé, je dors...")
            await asyncio.sleep(60)
            continue
        logger.info(f"[ROLLS] Nodes found: {list(app_globals.app_results.keys())}")
        for node_name, node_data in app_globals.app_results.items():
            wallets = node_data.get("wallets", {})
            logger.info(f"[ROLLS] Node '{node_name}' - wallets: {list(wallets.keys())}")
            if not wallets:
                logger.warning(f"[ROLLS] Node '{node_name}' has no wallets configured!")
                continue

            history.setdefault(node_name, {})

            for wallet_address in wallets:
                logger.info(f"[ROLLS] Checking rolls for {wallet_address} @ {node_name}")
                try:
                    # Appel Massa JSON-RPC
                    # Appel JSON-RPC
                    resp = await pull_http_api(
                        api_url=node_data["url"],
                        api_method="POST",
                        api_payload=json.dumps({
                            "jsonrpc": "2.0",
                            "method": "get_addresses",
                            "params": [[wallet_address]],
                            "id": 0
                        }),
                        api_content_type="application/json"
                    )
                    if not resp or "result" not in resp or "result" not in resp["result"] or not isinstance(resp["result"]["result"], list) or not resp["result"]["result"]:
                        logger.warning(f"[ROLLS] API result unusable for {wallet_address}@{node_name}: {resp}")
                        continue

                    addr_data = resp["result"]["result"][0]
                    active_rolls = int(addr_data.get("final_roll_count", 0) or 0)
                    candidate_rolls = int(addr_data.get("candidate_roll_count", 0) or 0)

                    now_iso = datetime.now().isoformat(timespec="seconds")

                    new_measure = {
                        "datetime": now_iso,
                        "active_rolls": active_rolls,
                        "candidate_rolls": candidate_rolls
                    }

                    wallet_hist = history[node_name].setdefault(wallet_address, [])
                    prev_measure = wallet_hist[-1] if wallet_hist else None

                    # Détection et alerte
                    for typ, field in [("actifs", "active_rolls"), ("candidats", "candidate_rolls")]:
                        if prev_measure and new_measure[field] != prev_measure[field]:
                            delta = new_measure[field] - prev_measure[field]
                            direction = "increase" if delta > 0 else "decrease"
                            emoji = "🟢" if delta > 0 else "🔴"
                            msg = (
                                f"{emoji} <b>{typ.capitalize()} rolls changed</b>\n"
                                f"👛 Wallet: <code>{wallet_address}</code>\n"
                                f"🏠 Node: <b>{node_name}</b>\n"
                                f"🗓 {now_iso}\n"
                                f"📈 Change: <b>{direction}</b> of {abs(delta)} roll(s)\n"
                                f"🎯 New total: <b>{new_measure[field]}</b> rolls {typ}"
                            )
                            await send_alert(
                                alert_type="wallet_roll_change",
                                node=node_name,
                                wallet=wallet_address,
                                level="info",
                                html=msg
                            )
                            logger.info(f"[ROLLS] {field} changed for {wallet_address}@{node_name}: {prev_measure[field]} -> {new_measure[field]}")

                    wallet_hist.append(new_measure)
                    # Garde uniquement les N derniers points
                    if len(wallet_hist) > MAX_HISTORY:
                        del wallet_hist[0:len(wallet_hist)-MAX_HISTORY]

                except Exception as e:
                    logger.error(f"[ROLLS] Error processing rolls for {wallet_address}@{node_name}: {e}")

        await save_json_history(history)
        await asyncio.sleep(polling_interval)
