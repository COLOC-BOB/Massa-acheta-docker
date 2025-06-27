# massa_acheta_docker/watchers/deferred_credits.py

import asyncio
import json
import os
from datetime import datetime
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert

WATCH_FILE = "watchers_state/deferred_credits_seen.json"
_save_lock = asyncio.Lock()

def load_json_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[DEFERRED] Could not load deferred credits watcher state: {str(e)}")
    return {}

async def save_json_history(history):
    async with _save_lock:
        tmp_file = WATCH_FILE + ".tmp"
        try:
            with open(tmp_file, "wt") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
            os.replace(tmp_file, WATCH_FILE)
        except Exception as e:
            logger.error(f"[DEFERRED] Could not save deferred credits watcher state: {str(e)}")

async def watch_deferred_credits(polling_interval=30):
    logger.info(f"[DEFERRED] JSON Watcher started")
    # Structure :
    # {
    #   "My node": {
    #     "AU12xxx...": [
    #         {"datetime": "...", "period": ..., "thread": ..., "amount": ...},
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

                    if (
                        not resp or
                        "result" not in resp or
                        "result" not in resp["result"] or
                        not isinstance(resp["result"]["result"], list) or
                        not resp["result"]["result"]
                    ):
                        continue

                    addr_info = resp["result"]["result"][0]
                    deferred_credits = addr_info.get("deferred_credits", [])

                    if wallet_address not in history[node_name]:
                        history[node_name][wallet_address] = []

                    # On récupère la liste des crédits déjà vus (clé = period, thread, amount, datetime)
                    credits_seen = {(c["period"], c["thread"], str(c["amount"])) for c in history[node_name][wallet_address]}

                    for credit in deferred_credits:
                        period = credit.get('slot', {}).get('period')
                        thread = credit.get('slot', {}).get('thread')
                        amount = str(credit.get('amount', 0))
                        now_iso = datetime.now().isoformat()

                        key_tuple = (period, thread, amount)
                        if key_tuple not in credits_seen:
                            # Ajout dans l'historique (datetime ISO)
                            entry = {
                                "datetime": now_iso,
                                "period": period,
                                "thread": thread,
                                "amount": amount
                            }
                            history[node_name][wallet_address].append(entry)
                            credits_seen.add(key_tuple)

                            # Notification via alert manager
                            message = (
                                f"💰 <b>New deferred credit detected</b>\n"
                                f"👛 Wallet: <code>{wallet_address}</code>\n"
                                f"🏠 Node: <b>{node_name}</b>\n"
                                f"⏳ Period: <b>{period}</b> / Thread: <b>{thread}</b>\n"
                                f"💸 Amount: <b>{amount} MAS</b>\n"
                                f"🕒 Added to history."
                            )
                            await send_alert(
                                alert_type="wallet_deferred_credit",
                                node=node_name,
                                wallet=wallet_address,
                                level="info",
                                html=message
                            )
                            logger.success(f"[DEFERRED] New credit for {wallet_address}@{node_name}: period={period}, thread={thread}, amount={amount}")

                except Exception as e:
                    logger.error(f"[DEFERRED] Error fetching wallet {wallet_address}: {str(e)}")

        await save_json_history(history)
        await asyncio.sleep(polling_interval)
