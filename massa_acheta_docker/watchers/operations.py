import asyncio
import json
import os
import time
from datetime import datetime
from loguru import logger
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert

WATCH_FILE = "watchers_state/operations_seen.json"

def load_history():
    if os.path.exists(WATCH_FILE):
        try:
            with open(WATCH_FILE, "rt") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Could not load operations history: {e}")
    return {}

def save_history(history):
    with open(WATCH_FILE, "wt") as f:
        json.dump(history, f, indent=2)

async def get_operation_details(node_url, op_id):
    try:
        resp = await pull_http_api(
            api_url=node_url,
            api_method="POST",
            api_payload=json.dumps({
                "jsonrpc": "2.0",
                "method": "get_operations",
                "params": [[op_id]],
                "id": 0
            }),
            api_content_type="application/json"
        )
        result = resp.get("result")
        if result and isinstance(result, list) and len(result) > 0:
            return result[0]
        else:
            logger.warning(f"Operation {op_id} not found on node {node_url}")
            return None
    except Exception as e:
        logger.error(f"Error fetching operation details for {op_id}: {e}")
        return None

async def watch_operations(polling_interval=30):
    logger.info("Watcher: operations started")
    history = load_history()

    while True:
        for node_name, node_data in app_globals.app_results.items():
            for wallet_address in node_data.get("wallets", {}):
                try:
                    resp = await pull_http_api(
                        api_url=app_globals.app_config['service']['mainnet_rpc_url'],
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
                    created_ops = result[0].get("created_operations", [])
                except Exception as e:
                    logger.error(f"Error fetching wallet {wallet_address}: {e}")
                    continue

                # Pour chaque opération créée
                for op_id in created_ops:
                    if op_id not in history:
                        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        op_details = await get_operation_details(app_globals.app_config['service']['mainnet_rpc_url'], op_id)
                        history[op_id] = {
                            "wallet": wallet_address,
                            "node": node_name,
                            "op_id": op_id,
                            "detected_at": int(time.time()),
                            "datetime": dt,
                            "details": op_details
                        }
                        save_history(history)

                        # Construction du message
                        message = (
                            f"📨 <b>Nouvelle opération créée</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"🆔 Opération: <code>{op_id}</code>\n"
                            f"🕒 {dt}\n"
                        )
                        # Ajoute les détails si disponibles
                        if op_details:
                            op_type = op_details.get("operation", {}).get("type", "unknown")
                            op_status = op_details.get("status", "unknown")
                            op_fee = op_details.get("operation", {}).get("fee", "-")
                            # Transaction classique :
                            if op_type == "Transaction":
                                to_addr = op_details.get("operation", {}).get("content", {}).get("recipient_address", "-")
                                amount = op_details.get("operation", {}).get("content", {}).get("amount", "-")
                                message += (
                                    f"\n💸 Type: {op_type}"
                                    f"\n➡️ To: <code>{to_addr}</code>"
                                    f"\n💰 Amount: <b>{amount}</b> MAS"
                                    f"\n🪙 Fee: <b>{op_fee}</b> MAS"
                                    f"\n⏳ Status: <b>{op_status}</b>"
                                )
                            else:
                                message += (
                                    f"\n🔎 Type: {op_type}"
                                    f"\n🪙 Fee: <b>{op_fee}</b> MAS"
                                    f"\n⏳ Status: <b>{op_status}</b>"
                                )

                        message += "\n🗂 Ajoutée à l'historique."
                        await send_alert(
                            alert_type="operation_created",
                            node=node_name,
                            wallet=wallet_address,
                            level="info",
                            html=message
                        )
                        logger.info(f"[OPERATION] New operation: {op_id} ({dt})")

        await asyncio.sleep(polling_interval)
