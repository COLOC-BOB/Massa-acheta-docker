from loguru import logger
import json
import app_globals
from alert_manager import send_alert
from telegram.queue import queue_telegram_message
from remotes_utils import pull_http_api, t_now


def format_html_message(lines):
    """Assemble une liste de lignes avec sauts de ligne HTML."""
    return "\n".join(lines)

def code(text):
    """Entoure du code HTML."""
    return f"<code>{text}</code>"

def bold(text):
    return f"<b>{text}</b>"

@logger.catch
async def check_node(node_name: str="") -> None:
    logger.debug(f"[NODE] -> check_node")

    payload = json.dumps(
        {
            "id": 0,
            "jsonrpc": "2.0",
            "method": "get_status",
            "params": []
        }
    )

    node_answer = {"error": "No response from remote HTTP API"}
    try:
        node_answer = await pull_http_api(
            api_url=app_globals.app_results[node_name]['url'],
            api_method="POST",
            api_payload=payload,
            api_root_element="result"
        )

        node_result = node_answer.get("result", None)
        if not node_result:
            raise Exception(f"Wrong answer from MASSA node API ({node_answer})")

        # Champs principaux
        node_chain_id = node_result.get("chain_id", "-")
        node_current_cycle = node_result.get("current_cycle", "-")
        node_id = node_result.get("node_id", "-")
        node_ip = node_result.get("node_ip", "-")
        version = node_result.get("version", "-")
        config = node_result.get("config", {})
        consensus_stats = node_result.get("consensus_stats", {})
        network_stats = node_result.get("network_stats", {})

        # Réseau
        active_node_count = network_stats.get("active_node_count", "-")
        known_peer_count = network_stats.get("known_peer_count", "-")
        in_connection_count = network_stats.get("in_connection_count", "-")
        out_connection_count = network_stats.get("out_connection_count", "-")
        banned_peer_count = network_stats.get("banned_peer_count", "-")

        # Consensus
        clique_count = consensus_stats.get("clique_count", "-")
        final_block_count = consensus_stats.get("final_block_count", "-")
        stale_block_count = consensus_stats.get("stale_block_count", "-")

        # Config (quelques exemples)
        thread_count = config.get("thread_count", "-")
        block_reward = config.get("block_reward", "-")
        roll_price = config.get("roll_price", "-")
        t0 = config.get("t0", "-")
        periods_per_cycle = config.get("periods_per_cycle", "-")

        # read node start time if provided
        node_start_time = node_result.get("start_time", None)
        if not node_start_time:
            node_start_time = node_result.get("node_start_time", 0)
        try:
            if node_start_time:
                node_start_time = int(float(node_start_time))
        except Exception:
            node_start_time = 0

    except BaseException as E:
        logger.warning(f"[NODE] Node '{node_name}' ({app_globals.app_results[node_name]['url']}) seems dead! ({E})")
        message_lines = []

        if app_globals.app_results[node_name]['last_status'] != False:
            message_lines = [
                f"🏠 Node: \"{node_name}\"",
                f"📍 <b>URL</b>: {app_globals.app_results[node_name]['url']}",
                "",
                f"☠ <b>OFFLINE / UNAVAILABLE</b>",
                "",
                f"🆔 Node ID: {code(app_globals.app_results[node_name].get('last_chain_id', '-'))}",
                f"🌐 IP: {code(app_globals.app_results[node_name].get('node_ip', '-'))}",
                "",
                f"💥 Exception: {code(str(E))}",
                "⚠️ Check node, network or firewall settings!"
            ]
 
            await send_alert(
                alert_type="node_offline",
                node=node_name,
                level="critical",
                html=format_html_message(message_lines),
                disable_web_page_preview=True
            )


        app_globals.app_results[node_name]['last_status'] = False
        app_globals.app_results[node_name]['last_result'] = node_result

    else:
        logger.info(f"[NODE] Node '{node_name}' ({app_globals.app_results[node_name]['url']}) seems online ({node_chain_id=})")
        message_lines = []

        # MESSAGE DÉTAILLÉ
        if app_globals.app_results[node_name]['last_status'] != True:
            message_lines = [
                f"🏠 Node: \"{bold(node_name)}\"",
                f"📍 <b>URL</b>: {app_globals.app_results[node_name]['url']}",
                "",
                f"🆔 Node ID: {code(node_id)}",
                f"🌐 IP: {code(node_ip)}",
                f"🔢 Chain ID: {bold(node_chain_id)}",
                f"🖥 Version: {bold(version)}",
                f"🌀 Cycle: {bold(node_current_cycle)}",
                "",
                f"⚙️ Threads: {thread_count} | Block reward: {block_reward} MAS | Roll price: {roll_price} MAS",
                f"⏱ t0: {t0} ms | Periods/cycle: {periods_per_cycle}",
                "",
                f"🌍 <b>Network</b>: {active_node_count} active nodes | {known_peer_count} known peers",
                f"➡️ IN: {in_connection_count} | ⬅️ OUT: {out_connection_count} | 🚫 Banned: {banned_peer_count}",
                "",
                f"⛓ Consensus: {clique_count} cliques | {final_block_count} final blocks | {stale_block_count} stale blocks"
            ]

            await send_alert(
                alert_type="node_online",
                node=node_name,
                level="info",
                html=format_html_message(message_lines),
                disable_web_page_preview=True
            )

        else:
            logger.info(f"[NODE] Node '{node_name}' ({app_globals.app_results[node_name]['url']}) seems online ({node_chain_id=})")

            # Si le numéro de cycle du node est < au réseau => ALERTE!
            if (node_current_cycle != "-" and 
                app_globals.massa_network['values']['current_cycle'] != "-" and
                int(node_current_cycle) < int(app_globals.massa_network['values']['current_cycle'])):
                message_lines = [
                    f"🏠 Node: \"{bold(node_name)}\"",
                    f"📍 <b>URL</b>: {app_globals.app_results[node_name]['url']}",
                    "",
                    "🌀 <b>Cycle number mismatch!</b>",
                    f"👁 Node cycle ID < network ({node_current_cycle} < {app_globals.massa_network['values']['current_cycle']})",
                    "",
                    "⚠️ Check node sync status!"
                ]
                await send_alert(
                    alert_type="node_cycle_mismatch",
                    node=node_name,
                    level="warning",
                      html=format_html_message(message_lines),
                    disable_web_page_preview=True
                )

        # Mise à jour des infos globales node
        app_globals.app_results[node_name]['last_status'] = True
        app_globals.app_results[node_name]['last_update'] = await t_now()
        app_globals.app_results[node_name]['last_chain_id'] = node_chain_id
        app_globals.app_results[node_name]['last_cycle'] = node_current_cycle
        app_globals.app_results[node_name]['last_result'] = node_result
        app_globals.app_results[node_name]['node_ip'] = node_ip
        app_globals.app_results[node_name]['version'] = version
        if node_start_time:
            app_globals.app_results[node_name]['start_time'] = node_start_time

    return


if __name__ == "__main__":
    pass
