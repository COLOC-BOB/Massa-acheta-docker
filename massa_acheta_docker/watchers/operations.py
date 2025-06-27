# massa_acheta_docker/watchers/operations.py

import asyncio
import json
import os
import time
from datetime import datetime
from loguru import logger

from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert
from watcher_utils import load_json_watcher, save_json_watcher
from watchers.watchers_control import is_watcher_enabled

WATCH_FILE = "watchers_state/operations_seen.json"

def log_short_ops(wallet_address, ops, label="created_operations", preview=10):
    n = len(ops)
    if n == 0:
        logger.debug(f"[OPERATIONS] {wallet_address} {label}: [aucune opération]")
    else:
        short_list = ops[:preview] + (["..."] if n > preview else [])
        logger.debug(f"[OPERATIONS] {wallet_address} {label} (total {n}): {short_list}")

async def get_operation_details(op_id, node_url):
    payload = {
        "jsonrpc": "2.0",
        "method": "get_operations",
        "params": [[op_id]],
        "id": 0
    }
    try:
        resp = await pull_http_api(
            api_url=node_url,
            api_method="POST",
            api_payload=payload,
            api_content_type="application/json"
        )
        # Le résultat de l'API peut varier : dict avec clé "result", ou liste brute
        op_list = None
        if "result" in resp and isinstance(resp["result"], dict) and "result" in resp["result"]:
            op_list = resp["result"]["result"]
        elif "result" in resp and isinstance(resp["result"], list):
            op_list = resp["result"]
        else:
            op_list = []
        if op_list and len(op_list) > 0:
            return op_list[0]
    except Exception as e:
        logger.error(f"[OPERATIONS] Erreur lors de la récupération du détail op {op_id}: {str(e)}")
    return None

def format_operation_details(op_detail):
    if not op_detail:
        return "<i>Détail non disponible</i>"

    op_status = op_detail.get("op_exec_status", "unknown")
    op_obj = op_detail.get("operation", {})
    op_content = op_obj.get("content", {})    # <<<<<< Correctif majeur ici !
    fee = op_content.get("fee", "-")
    expire_period = op_content.get("expire_period", "-")
    op_types = op_content.get("op", {})       # <<<<<< Et ici

    logger.debug(f"[OPERATIONS] op_types: {op_types}")
    logger.debug(f"[OPERATIONS] Operation details raw: {json.dumps(op_detail, indent=2, ensure_ascii=False)}")
    logger.debug(f"[OPERATIONS] op_obj: {json.dumps(op_obj, indent=2, ensure_ascii=False)}")
    logger.debug(f"[OPERATIONS] content: {json.dumps(op_content, indent=2, ensure_ascii=False)}")

    if "Transaction" in op_types:
        op_type = "Transaction"
        tx = op_types["Transaction"]
        to_addr = tx.get("recipient_address", "-")
        amount = tx.get("amount", "-")
        return (
            f"\n💸 <b>Transaction</b>"
            f"\n➡️ To: <code>{to_addr}</code>"
            f"\n💰 Amount: <b>{amount}</b> MAS"
            f"\n🪙 Fee: <b>{fee}</b> MAS"
            f"\n⏳ Status: <b>{op_status}</b>"
        )
    elif "RollBuy" in op_types:
        op_type = "RollBuy"
        count = op_types["RollBuy"].get("roll_count", "-")
        return (
            f"\n🎲 <b>Rolls purchase</b>"
            f"\n🔢 Quantity: <b>{count}</b>"
            f"\n🪙 Fee: <b>{fee}</b> MAS"
            f"\n⏳ Status: <b>{op_status}</b>"
        )
    elif "RollSell" in op_types:
        op_type = "RollSell"
        count = op_types["RollSell"].get("roll_count", "-")
        return (
            f"\n💸 <b>Rolls sale</b>"
            f"\n🔢 Quantity: <b>{count}</b>"
            f"\n🪙 Fee: <b>{fee}</b> MAS"
            f"\n⏳ Status: <b>{op_status}</b>"
        )
    elif "ExecuteSC" in op_types:
        op_type = "ExecuteSC"
        sc = op_types["ExecuteSC"]
        max_gas = sc.get("max_gas", "-")
        coins = sc.get("coins", "-")
        data = sc.get("data", "-")
        return (
            f"\n📜 <b>Deploy/Execute SC</b>"
            f"\n🪙 Coins: <b>{coins}</b> MAS"
            f"\n⛽ Max Gas: <b>{max_gas}</b>"
            f"\n📦 Data: <code>{data}</code>"
            f"\n🪙 Fee: <b>{fee}</b> MAS"
            f"\n⏳ Status: <b>{op_status}</b>"
        )
    elif "CallSC" in op_types:
        op_type = "CallSC"
        call = op_types["CallSC"]
        target_addr = call.get("target_addr", "-")
        target_func = call.get("target_func", "-")
        param = call.get("param", "-")
        max_gas = call.get("max_gas", "-")
        coins = call.get("coins", "-")
        return (
            f"\n📞 <b>SC call</b>"
            f"\n🎯 SC: <code>{target_addr}</code>"
            f"\n🛠 Function: <b>{target_func}</b>"
            f"\n🪙 Coins: <b>{coins}</b> MAS"
            f"\n⛽ Max Gas: <b>{max_gas}</b>"
            f"\n🪙 Fee: <b>{fee}</b> MAS"
            f"\n⏳ Status: <b>{op_status}</b>"
        )
    else:
        return (
            f"\n🔎 <b>Unknown type</b>: <code>{op_types}</code>"
            f"\n🪙 Fee: <b>{fee}</b> MAS"
            f"\n⏳ Status: <b>{op_status}</b>"
        )

async def watch_operations(polling_interval=30):
    try:
        previous_ops = load_json_watcher(WATCH_FILE, {})
    except Exception as e:
        logger.error(f"[OPERATIONS] Erreur chargement {WATCH_FILE} : {str(e)}")
        previous_ops = {}

    logger.info(f"[OPERATIONS] Watcher: operations started")
    while True:
        if not is_watcher_enabled("operations"):
            logger.info(f"[OPERATIONS] Désactivé, je dors...")
            await asyncio.sleep(60)
            continue

        for node_name, node_data in app_globals.app_results.items():
            node_url = node_data.get("url") or app_globals.app_config["service"]["mainnet_rpc_url"]
            for wallet_address in node_data.get("wallets", {}):
                logger.debug(f"[OPERATIONS] Checking wallet {wallet_address} on node {node_name}")
                try:
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "get_addresses",
                        "params": [[wallet_address]],
                        "id": 0
                    }
                    resp = await pull_http_api(
                        api_url=node_url,
                        api_method="POST",
                        api_payload=payload,
                        api_content_type="application/json"
                    )
                except Exception as e:
                    logger.warning(f"[OPERATIONS] API error for {wallet_address}@{node_name}: {str(e)}")
                    continue

                # Compatibilité: API peut répondre .result.result ou .result
                result = resp.get("result", {}).get("result") if isinstance(resp.get("result", {}), dict) else resp.get("result")
                if not result or not isinstance(result, list) or not result[0]:
                    logger.debug(f"[OPERATIONS] {wallet_address}: résultat API inexploitable")
                    continue
                if "created_operations" not in result[0]:
                    logger.debug(f"[OPERATIONS] {wallet_address}: champ 'created_operations' absent dans la réponse")
                    continue
                created_ops = result[0]["created_operations"]
                log_short_ops(wallet_address, created_ops, label="created_operations")

                old_ops = previous_ops.get(wallet_address, [])
                log_short_ops(wallet_address, old_ops, label="old_operations")
                new_ops = [o for o in created_ops if o not in old_ops]
                log_short_ops(wallet_address, new_ops, label="new_operations")

                if not created_ops or len(created_ops) == 0:
                    logger.warning(f"[OPERATIONS] {wallet_address}@{node_name}: Pas d'opérations créées (created_operations vide). Peut-être une limitation du node public.")
                    continue

                if new_ops:
                    for op_id in new_ops:
                        op_detail = await get_operation_details(op_id, node_url)
                        dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        message = (
                            f"📨 <b>New operation created</b>\n"
                            f"👛 Wallet: <code>{wallet_address}</code>\n"
                            f"🏠 Node: <b>{node_name}</b>\n"
                            f"🆔 Operation: <code>{op_id}</code>\n"
                            f"🕒 {dt}\n"
                            f"{format_operation_details(op_detail)}\n"
                            f"🗂 Added to history."
                        )
                        await send_alert(
                            alert_type="operation_created",
                            node=node_name,
                            wallet=wallet_address,
                            level="info",
                            html=message
                        )
                        logger.success(f"[OPERATIONS] Nouvelle opération: {op_id} ({dt})")

                    previous_ops[wallet_address] = created_ops
                    try:
                        save_json_watcher(WATCH_FILE, previous_ops)
                        logger.info(f"{WATCH_FILE} mis à jour pour {wallet_address} ({len(created_ops)} opérations connues)")
                    except Exception as e:
                        logger.error(f"[OPERATIONS] Erreur sauvegarde {WATCH_FILE}: {str(e)}")

        await asyncio.sleep(polling_interval)
