# massa_acheta_docker/watchers/balance.py

import asyncio
import json
import os
from datetime import datetime
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert

WATCH_FILE = "watchers_state/balances_seen.json"
_save_lock = asyncio.Lock()

def load_json_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[BALANCE] Could not load balance watcher state: {e}")
    return {}

async def save_json_history(history):
    async with _save_lock:
        tmp_file = WATCH_FILE + ".tmp"
        try:
            with open(tmp_file, "wt") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, WATCH_FILE)
        except Exception as e:
            logger.error(f"[BALANCE] Could not save balance watcher state: {e}")

async def watch_balance(polling_interval=30):
    logger.info(f"[BALANCE] JSON Watcher started")
    # Structure :
    # {
    #   "My node": {
    #     "AU12xxx...": [
    #         {"datetime": "...", "balance": ...},
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

                    # Correction ici !
                    if (
                        not resp or
                        "result" not in resp or
                        "result" not in resp["result"] or
                        not isinstance(resp["result"]["result"], list) or
                        not resp["result"]["result"]
                    ):
                        continue

                    addr_data = resp["result"]["result"][0]
                    final_balance = float(addr_data.get("final_balance", 0))


                    # Init de la liste d'observations
                    if wallet_address not in history[node_name]:
                        history[node_name][wallet_address] = []

                    wallet_history = history[node_name][wallet_address]
                    prev = wallet_history[-1] if wallet_history else None

                    # Détection du changement de balance
                    if prev and final_balance != prev["balance"]:
                        now_iso = datetime.now().isoformat()
                        delta = final_balance - prev["balance"]
                        direction = "Hausse" if delta > 0 else "Baisse"
                        emoji = "🟢" if delta > 0 else "🔴"
                        message = (
                            f"{emoji} <b>Changement de balance détecté</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"🗓 {now_iso}\n"
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
                        logger.info(f"[BALANCE] Change for {wallet_address}@{node_name}: {prev['balance']} -> {final_balance}")

                    # Ajoute à l'historique (toujours)
                    entry = {
                        "datetime": datetime.now().isoformat(),
                        "balance": final_balance
                    }
                    history[node_name][wallet_address].append(entry)

                except Exception as e:
                    logger.error(f"[BALANCE] Error processing balance for {wallet_address}@{node_name}: {str(e)}")

        await save_json_history(history)
        await asyncio.sleep(polling_interval)
