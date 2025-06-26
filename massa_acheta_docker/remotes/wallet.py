from loguru import logger

import json
from alert_manager import send_alert
from app_config import app_config
import app_globals

from remotes_utils import pull_http_api, get_short_address, t_now

def format_html_message(lines):
    return "\n".join(lines)

def code(text):
    return f"<code>{text}</code>"

def bold(text):
    return f"<b>{text}</b>"

@logger.catch
async def check_wallet(node_name: str="", wallet_address: str="") -> None:
    logger.debug(f"[WALLET] -> check_wallet")

    if app_globals.app_results[node_name]['last_status'] != True:
        logger.warning(f"[WALLET] Will not watch wallet '{wallet_address}'@'{node_name}' because of its offline")

        app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] = False
        app_globals.app_results[node_name]['wallets'][wallet_address]['last_result'] = {"error": "Host node is offline"}
        return

    payload = json.dumps({
        "id": 0,
        "jsonrpc": "2.0",
        "method": "get_addresses",
        "params": [[wallet_address]]
    })

    wallet_answer = {"error": "No response from remote HTTP API"}
    try:
        wallet_answer = await pull_http_api(
            api_url=app_globals.app_results[node_name]['url'],
            api_method="POST",
            api_payload=payload,
            api_root_element="result"
        )

        wallet_result = wallet_answer.get("result", None)
        if not wallet_result:
            raise Exception(f"Wrong answer from MASSA node API ({wallet_answer})")

        wallet_result = wallet_result[0]
        wallet_result_address = wallet_result.get("address", None)
        if wallet_result_address != wallet_address:
            raise Exception(f"Bad address received from MASSA node API: '{wallet_result_address}' (expected '{wallet_address}')")

        wallet_final_balance = float(wallet_result.get("final_balance", 0))
        wallet_final_balance = round(wallet_final_balance, 4)
        wallet_candidate_rolls = int(wallet_result.get("candidate_roll_count", 0))
        wallet_cycle_infos = wallet_result.get("cycle_infos", [])
        if not wallet_cycle_infos:
            raise Exception(f"Bad cycle_infos for wallet '{wallet_address}'")

        wallet_active_rolls = wallet_cycle_infos[-1].get("active_rolls", 0)
        wallet_operated_blocks = sum(ci.get("ok_count", 0) for ci in wallet_cycle_infos)
        wallet_missed_blocks = sum(ci.get("nok_count", 0) for ci in wallet_cycle_infos)

    except BaseException as E:
        logger.warning(f"[WALLET] Error watching wallet '{wallet_address}' on '{node_name}': ({E})")

        if app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] != False:
            message_lines = [
                f"🏠 Node: \"{node_name}\"",
                f"📍 {app_globals.app_results[node_name]['url']}",
                f"🚨 Cannot get info for wallet: <code>{wallet_address}</code>",
                f"💥 Exception: {code(str(E))}",
                "⚠ Check wallet address or node settings!"
            ]
            logger.warning(f"[WALLET] Wallet '{wallet_address}'@'{node_name}' RPC error: {str(E)}")
            await send_alert(
                alert_type="wallet_rpc_error",
                node=node_name,
                wallet=wallet_address,
                level="warning",
                html=format_html_message(message_lines),
                disable_web_page_preview=True
            )

        app_globals.app_results[node_name]['wallets'][wallet_address]['last_status'] = False
        app_globals.app_results[node_name]['wallets'][wallet_address]['last_result'] = wallet_answer
        return

    # ------ WALLET OK : on compare les stats avec la dernière fois ------
    prev = app_globals.app_results[node_name]['wallets'][wallet_address]
    changed = False

    # 1) Balance a baissé ?
    if wallet_final_balance < prev['final_balance']:
        changed = True
        message_lines = [
            f"🏠 Node: \"{node_name}\"",
            f"📍 {app_globals.app_results[node_name]['url']}",
            f"💸 <b>Balance decreased!</b>",
            f"👛 Wallet: <code>{wallet_address}</code>",
            f"💰 {prev['final_balance']} → {wallet_final_balance} MAS"
        ]
        await send_alert(
            alert_type="wallet_balance_drop",
            node=node_name,
            wallet=wallet_address,
            level="warning",
            html=format_html_message(message_lines),
            disable_web_page_preview=True
        )

    # 2) Candidate rolls changé ?
    if wallet_candidate_rolls != prev['candidate_rolls']:
        changed = True
        message_lines = [
            f"🏠 Node: \"{node_name}\"",
            f"📍 {app_globals.app_results[node_name]['url']}",
            f"🗞 <b>Candidate rolls changed</b>",
            f"👛 Wallet: <code>{wallet_address}</code>",
            f"{prev['candidate_rolls']} → {wallet_candidate_rolls}"
        ]
        await send_alert(
            alert_type="wallet_roll_change",
            node=node_name,
            wallet=wallet_address,
            level="info",
            html=format_html_message(message_lines),
            disable_web_page_preview=True
        )

    # 3) Active rolls changé ?
    if wallet_active_rolls != prev['active_rolls']:
        changed = True
        message_lines = [
            f"🏠 Node: \"{node_name}\"",
            f"📍 {app_globals.app_results[node_name]['url']}",
            f"🗞 <b>Active rolls changed</b>",
            f"👛 Wallet: <code>{wallet_address}</code>",
            f"{prev['active_rolls']} → {wallet_active_rolls}"
        ]
        await send_alert(
            alert_type="wallet_roll_change",
            node=node_name,
            wallet=wallet_address,
            level="info",
            html=format_html_message(message_lines),
            disable_web_page_preview=True
        )

    # 4) Nouveaux blocs manqués ?
    if wallet_missed_blocks > prev['missed_blocks']:
        delta = wallet_missed_blocks - prev['missed_blocks']
        changed = True
        message_lines = [
            f"🏠 Node: \"{node_name}\"",
            f"📍 {app_globals.app_results[node_name]['url']}",
            f"🥊 <b>{delta} New missed block(s)</b>",
            f"👛 Wallet: <code>{wallet_address}</code>",
            f"Total missed: {wallet_missed_blocks}"
        ]
        await send_alert(
            alert_type="wallet_block_miss",
            node=node_name,
            wallet=wallet_address,
            level="warning",
            html=format_html_message(message_lines),
            disable_web_page_preview=True
        )

    # 5) Nouveaux blocs produits ?
    if 'produced_blocks' in prev:
        prev_blocks = prev['produced_blocks']
    else:
        prev_blocks = wallet_operated_blocks
    if wallet_operated_blocks > prev_blocks:
        delta = wallet_operated_blocks - prev_blocks
        message_lines = [
            f"🏠 Node: \"{node_name}\"",
            f"📍 {app_globals.app_results[node_name]['url']}",
            f"✅ <b>{delta} New block(s) produced</b>",
            f"👛 Wallet: <code>{wallet_address}</code>",
            f"Total produced: {wallet_operated_blocks}"
        ]
        logger.info(f"[WALLET] Wallet '{wallet_address}'@'{node_name}' produced {delta} new block(s)")
        await send_alert(
            alert_type="wallet_block_produced",
            node=node_name,
            wallet=wallet_address,
            level="info",
            html=format_html_message(message_lines),
            disable_web_page_preview=True
        )

    # --- Mise à jour des valeurs (toujours, même si rien n’a changé) ---
    time_now = await t_now()
    w = app_globals.app_results[node_name]['wallets'][wallet_address]
    w['last_status'] = True
    w['last_update'] = time_now
    w['final_balance'] = wallet_final_balance
    w['candidate_rolls'] = wallet_candidate_rolls
    w['active_rolls'] = wallet_active_rolls
    w['missed_blocks'] = wallet_missed_blocks
    w['produced_blocks'] = wallet_operated_blocks
    w['last_result'] = wallet_result

    # Ajout au stat historique
    final_cycle = wallet_cycle_infos[-2] if len(wallet_cycle_infos) > 1 else wallet_cycle_infos[-1]
    wallet_last_cycle = final_cycle.get("cycle", 0)
    wallet_last_cycle_operated_blocks = final_cycle.get("ok_count", 0)
    wallet_last_cycle_missed_blocks = final_cycle.get("nok_count", 0)

    w['stat'].append({
        "time": time_now,
        "cycle": wallet_last_cycle,
        "balance": wallet_final_balance,
        "rolls": wallet_active_rolls,
        "total_rolls": app_globals.massa_network['values']['total_staked_rolls'],
        "ok_blocks": wallet_last_cycle_operated_blocks,
        "nok_blocks": wallet_last_cycle_missed_blocks,
        "produced_blocks": wallet_operated_blocks
    })

    logger.info(f"[WALLET] Stat updated for wallet '{wallet_address}'@'{node_name}'")
    return

if __name__ == "__main__":
    pass
