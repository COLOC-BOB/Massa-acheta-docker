# massa_acheta_docker/watchers/deferred_credits.py
import asyncio
import json
import time
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert
import os

WATCH_FILE = "watchers_state/deferred_credits_seen.json"

def load_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Could not load deferred credits history: {e}")
    return {}

def save_history(history):
    with open(WATCH_FILE, "wt") as f:
        json.dump(history, f, indent=2)

async def watch_deferred_credits(polling_interval=30):
    logger.info("Watcher: deferred credits started")
    history = load_history()

    while True:
        for node_name, node_data in app_globals.app_results.items():
            for wallet_address in node_data.get("wallets", {}):
                # Appel API pour obtenir les infos du wallet
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
                    deferred_credits = result[0].get("deferred_credits", [])
                except Exception as e:
                    logger.error(f"Error fetching wallet {wallet_address}: {e}")
                    continue

                for credit in deferred_credits:
                    period = credit.get('slot', {}).get('period')
                    thread = credit.get('slot', {}).get('thread')
                    amount = credit.get('amount', 0)
                    # Id unique pour chaque crédit différé
                    key = f"{wallet_address}:{period}:{thread}:{amount}"
                    if key not in history:
                        # Historisation
                        history[key] = {
                            "wallet": wallet_address,
                            "node": node_name,
                            "period": period,
                            "thread": thread,
                            "amount": amount,
                            "detected_at": int(time.time())
                        }
                        save_history(history)
                        # Notification via alert manager
                        message = (
                            f"💰 <b>Nouveau crédit différé détecté</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"⏳ Période: <b>{period}</b> / Thread: <b>{thread}</b>\n"
                            f"💸 Montant: <b>{amount} MAS</b>\n"
                            f"🕒 Ajouté à l'historique."
                        )
                        await send_alert(
                            alert_type="wallet_deferred_credit",
                            node=node_name,
                            wallet=wallet_address,
                            level="info",
                            html=message
                        )
                        logger.success(f"[DEFERRED] New credit: {key}")

        await asyncio.sleep(polling_interval)

# --- Pour lancer ce watcher en tâche asynchrone depuis ton main (exemple) ---
# asyncio.create_task(watch_deferred_credits())
