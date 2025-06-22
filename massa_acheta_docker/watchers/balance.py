# massa_acheta_docker/watchers/balance.py
import asyncio
import json
import os
import time
from datetime import datetime
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert

WATCH_FILE = "watchers_state/balance_seen.json"

def load_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Could not load balance history: {e}")
    return {}

def save_history(history):
    with open(WATCH_FILE, "wt") as f:
        json.dump(history, f, indent=2)

async def watch_balance(polling_interval=30):
    logger.info("Watcher: balance started")
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
                    final_balance = float(addr_data.get("final_balance", 0))
                    prev_balance = float(history.get(wallet_address, {}).get("final_balance", 0))

                    if prev_balance != 0 and final_balance != prev_balance:
                        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        delta = final_balance - prev_balance
                        direction = "Hausse" if delta > 0 else "Baisse"
                        emoji = "🟢" if delta > 0 else "🔴"
                        message = (
                            f"{emoji} <b>Changement de balance détecté</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"🗓 {dt}\n"
                            f"💸 {direction} de <b>{abs(delta):,.4f} MAS</b>\n"
                            f"💰 Nouveau solde : <b>{final_balance:,.4f} MAS</b>"
                        )
                        await send_alert(
                            alert_type="wallet_balance_drop" if delta < 0 else "wallet_balance_up",
                            node=node_name,
                            wallet=wallet_address,
                            level="info",
                            html=message
                        )
                        logger.info(f"[BALANCE] Change for {wallet_address}: {prev_balance} -> {final_balance}")

                    # Toujours enregistrer l'état courant
                    history[wallet_address] = {
                        "final_balance": final_balance,
                        "last_update": int(time.time())
                    }
                    save_history(history)

                except Exception as e:
                    logger.error(f"Error processing balance for {wallet_address}: {e}")

        await asyncio.sleep(polling_interval)
