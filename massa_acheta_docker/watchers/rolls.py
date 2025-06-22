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

def load_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Could not load rolls history: {e}")
    return {}

def save_history(history):
    with open(WATCH_FILE, "wt") as f:
        json.dump(history, f, indent=2)

async def watch_rolls(polling_interval=30):
    logger.info("Watcher: rolls started")
    history = load_history()
    if not isinstance(history, dict):
        history = {}

    while True:
        for node_name, node_data in app_globals.app_results.items():
            for wallet_address in node_data.get("wallets", {}):
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
                    active_rolls = addr_data.get("final_roll_count", 0)
                    candidate_rolls = addr_data.get("candidate_roll_count", 0)

                    prev = history.get(wallet_address, {})
                    prev_active = prev.get("active_rolls", None)
                    prev_candidate = prev.get("candidate_rolls", None)

                    # Détection de changement de rolls actifs
                    if prev_active is not None and active_rolls != prev_active:
                        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        delta = int(active_rolls) - int(prev_active)
                        direction = "gain" if delta > 0 else "perte"
                        emoji = "🟢" if delta > 0 else "🔴"
                        message = (
                            f"{emoji} <b>Changement de rolls actifs</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"🗓 {dt}\n"
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
                        logger.info(f"[ROLLS] Active rolls changed for {wallet_address}: {prev_active} -> {active_rolls}")

                    # Détection de changement de rolls candidats
                    if prev_candidate is not None and candidate_rolls != prev_candidate:
                        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        delta = int(candidate_rolls) - int(prev_candidate)
                        direction = "gain" if delta > 0 else "perte"
                        emoji = "🟢" if delta > 0 else "🔴"
                        message = (
                            f"{emoji} <b>Changement de rolls candidats</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"🗓 {dt}\n"
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
                        logger.info(f"[ROLLS] Candidate rolls changed for {wallet_address}: {prev_candidate} -> {candidate_rolls}")

                    # Toujours enregistrer l'état courant
                    history[wallet_address] = {
                        "active_rolls": int(active_rolls),
                        "candidate_rolls": int(candidate_rolls),
                        "last_update": int(time.time())
                    }
                    save_history(history)

                except Exception as e:
                    logger.error(f"Error processing rolls for {wallet_address}: {e}")

        await asyncio.sleep(polling_interval)
