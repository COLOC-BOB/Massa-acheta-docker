# massa_acheta_docker/watchers/rolls.py

import asyncio
import json
import os
import time
from datetime import datetime
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert

WATCH_FILE = "watchers_state/rolls_seen.json"
_save_lock = asyncio.Lock()

def load_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[ROLLS] Could not load rolls history: {e}")
    return {}

async def save_history(history):
    async with _save_lock:
        tmp_file = WATCH_FILE + ".tmp"
        try:
            with open(tmp_file, "wt") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, WATCH_FILE)
        except Exception as e:
            logger.error(f"[ROLLS] Could not save rolls history: {e}")

async def watch_rolls(polling_interval=30):
    logger.info("[ROLLS] Watcher: rolls started")
    history = load_history()
    if not isinstance(history, dict):
        history = {}

    while True:
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
                    result = resp.get("result")
                    if not result or not isinstance(result, list):
                        continue

                    addr_data = result[0]
                    active_rolls = int(addr_data.get("final_roll_count", 0))
                    candidate_rolls = int(addr_data.get("candidate_roll_count", 0))

                    prev = history[node_name].get(wallet_address, {})
                    prev_active = prev.get("active_rolls")
                    prev_candidate = prev.get("candidate_rolls")

                    now_dt = datetime.now()
                    now_fmt = now_dt.strftime("%Y-%m-%d %H:%M:%S")

                    # Détection de changement de rolls actifs
                    if prev_active is not None and active_rolls != prev_active:
                        delta = active_rolls - prev_active
                        direction = "gain" if delta > 0 else "perte"
                        emoji = "🟢" if delta > 0 else "🔴"
                        message = (
                            f"{emoji} <b>Changement de rolls actifs</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"🗓 {now_fmt}\n"
                            f"📈 Variation : <b>{direction}</b> de {abs(delta)} roll(s)\n"
                            f"🎯 Nouveau total : <b>{active_rolls}</b> rolls actifs"
                        )
                        await send_alert(
                            alert_type="wallet_roll_change",
                            node=node_name,
                            wallet=wallet_address,
                            level="info",
                            html=message
                        )
                        logger.info(f"[ROLLS] Active rolls changed for {wallet_address}@{node_name}: {prev_active} -> {active_rolls}")

                    # Détection de changement de rolls candidats
                    if prev_candidate is not None and candidate_rolls != prev_candidate:
                        delta = candidate_rolls - prev_candidate
                        direction = "gain" if delta > 0 else "perte"
                        emoji = "🟢" if delta > 0 else "🔴"
                        message = (
                            f"{emoji} <b>Changement de rolls candidats</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"🗓 {now_fmt}\n"
                            f"📈 Variation : <b>{direction}</b> de {abs(delta)} roll(s)\n"
                            f"🎯 Nouveau total : <b>{candidate_rolls}</b> rolls candidats"
                        )
                        await send_alert(
                            alert_type="wallet_roll_change",
                            node=node_name,
                            wallet=wallet_address,
                            level="info",
                            html=message
                        )
                        logger.info(f"[ROLLS] Candidate rolls changed for {wallet_address}@{node_name}: {prev_candidate} -> {candidate_rolls}")

                    # Toujours enregistrer l'état courant
                    history[node_name][wallet_address] = {
                        "active_rolls": active_rolls,
                        "candidate_rolls": candidate_rolls,
                        "last_update": int(time.time()),
                        "last_update_iso": now_dt.isoformat(),
                    }

                except Exception as e:
                    logger.error(f"[ROLLS] Error processing rolls for {wallet_address}@{node_name}: {e}")

        await save_history(history)
        await asyncio.sleep(polling_interval)
