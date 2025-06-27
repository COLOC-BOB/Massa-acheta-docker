#massa_acheta_docker/remotes/heartbeat.py
from loguru import logger
import asyncio

from app_config import app_config
import app_globals

from alert_manager import send_alert
from remotes_utils import get_last_seen, get_short_address, get_rewards_mas_day, get_duration

def html_link(text, url):
    return f'<a href="{url}">{text}</a>'

def format_wallet_line(wallet_address, balance, produced_blocks, last_cycle, explorer_url):
    return (
        f"⦙… {html_link(wallet_address, explorer_url)} "
        f"( {balance} MAS | {produced_blocks} OK | cycle {last_cycle} )"
    )

def format_wallet_line_unknown(wallet_address, explorer_url):
    return (
        f"⦙… {html_link(wallet_address, explorer_url)} "
        f"( ? MAS | ? OK | cycle ? )"
    )

async def heartbeat() -> None:
    logger.debug(f"[HEARTBEAT] -> heartbeat")

    try:
        while True:
            logger.info(f"[HEARTBEAT] Sleeping for {app_config['service']['heartbeat_period_hours'] * 60 * 60} seconds...")
            await asyncio.sleep(app_config['service']['heartbeat_period_hours'] * 60 * 60)
            logger.info(f"[HEARTBEAT] Heartbeat planner schedule time")

            computed_rewards = await get_rewards_mas_day(rolls_number=100)

            heartbeat_list = []
            heartbeat_list.append(
                "📚 <b>MASSA network info:</b>"
                f" 👥 Total stakers: <b>{app_globals.massa_network['values'].get('total_stakers', '?'):,}</b>"
                f" 🗞 Total staked rolls: <b>{app_globals.massa_network['values'].get('total_staked_rolls', '?'):,}</b>"
                f"🪙 Estimated rewards for 100 Rolls ≈ <b>{computed_rewards:,} MAS / Day</b>"
                f"👁 Info updated: {await get_last_seen(last_time=app_globals.massa_network['values'].get('last_updated'))}"
            )

            # Résumé global
            total_nodes = len(app_globals.app_results)
            online_nodes = sum(1 for n in app_globals.app_results.values() if n.get('last_status') == True)
            offline_nodes = total_nodes - online_nodes
            heartbeat_list.append(
                f"🖥️ <b>Node summary:</b> {online_nodes} online / {offline_nodes} offline (total {total_nodes})"
            )

            # Séparer nodes online/offline
            nodes_online = [n for n in app_globals.app_results if app_globals.app_results[n].get('last_status') == True]
            nodes_offline = [n for n in app_globals.app_results if app_globals.app_results[n].get('last_status') != True]

            if total_nodes == 0:
                heartbeat_list.append("⭕ Node list is empty")

            # Section ONLINE
            if nodes_online:
                heartbeat_list.append("\n🟢 <b>Online nodes:</b>")
                for node_name in nodes_online:
                    node = app_globals.app_results[node_name]
                    heartbeat_list.append(f"\n🏠 <b>Node:</b> \"{node_name}\"")
                    heartbeat_list.append(f"\n📍 {node.get('url', '?')}")
                    version = node.get('version', '?')
                    node_ip = node.get('node_ip', '?')
                    chain_id = node.get('last_chain_id', '?')
                    last_seen = await get_last_seen(node.get('last_update'))
                    node_uptime = await get_duration(
                        start_time=node.get('start_time', 0),
                        show_days=True
                    )
                    # Infos réseau/stat (issus du get_status)
                    network_stats = node.get('last_result', {}).get('network_stats', {})
                    in_con = network_stats.get('in_connection_count', '?')
                    out_con = network_stats.get('out_connection_count', '?')
                    peers = network_stats.get('known_peer_count', '?')
                    banned = network_stats.get('banned_peer_count', '?')

                    consensus = node.get('last_result', {}).get('consensus_stats', {})
                    final_blocks = consensus.get('final_block_count', '?')
                    stale_blocks = consensus.get('stale_block_count', '?')

                    heartbeat_list.append(
                        f"\n🌿 <b>Status:</b> Online (uptime {node_uptime}, last update {last_seen})"
                    )
                    heartbeat_list.append(
                        f"\n🔢 Version: <b>{version}</b> | Chain ID: <b>{chain_id}</b> | IP: <b>{node_ip}</b>"
                    )
                    heartbeat_list.append(
                        f"\n🌐 Network: {peers} peers, {in_con} in / {out_con} out, 🚫 {banned} banned"
                    )
                    heartbeat_list.append(
                        f"\n⛓️ Consensus: {final_blocks} final / {stale_blocks} stale blocks"
                    )

                    num_wallets = len(node['wallets'])
                    if num_wallets == 0:
                        heartbeat_list.append("\n⭕ No wallets attached")
                    else:
                        heartbeat_list.append(f"\n👛 {num_wallets} wallet(s) attached:")
                        wallet_lines = []
                        for wallet_address in node['wallets']:
                            w = node['wallets'][wallet_address]
                            explorer_url = f"{app_config['service']['mainnet_explorer_url']}/address/{wallet_address}"
                            short_addr = await get_short_address(address=wallet_address)
                            if w.get('last_status') == True:
                                balance = w.get('final_balance', '?')
                                produced_blocks = w.get('produced_blocks', '?')
                                last_cycle = w.get('last_cycle', '?')
                                wallet_lines.append(
                                    format_wallet_line(short_addr, balance, produced_blocks, last_cycle, explorer_url)
                                )
                            else:
                                wallet_lines.append(
                                    format_wallet_line_unknown(short_addr, explorer_url)
                                )
                        heartbeat_list.append("\n".join(wallet_lines))
                    heartbeat_list.append("\n")

            # Section OFFLINE
            if nodes_offline:
                heartbeat_list.append("\n🔴 <b>Offline nodes:</b>")
                for node_name in nodes_offline:
                    node = app_globals.app_results[node_name]
                    heartbeat_list.append(f"\n🏠 <b>Node:</b> \"{node_name}\"")
                    heartbeat_list.append(f"\n📍 {node.get('url', '?')}")
                    last_seen = await get_last_seen(node.get('last_update'))
                    heartbeat_list.append(f"\n☠️ <b>Status:</b> Offline (last seen {last_seen})")
                    version = node.get('version', '?')
                    node_ip = node.get('node_ip', '?')
                    chain_id = node.get('last_chain_id', '?')
                    heartbeat_list.append(
                        f"\n🔢 Version: <b>{version}</b> | Chain ID: <b>{chain_id}</b> | IP: <b>{node_ip}</b>"
                    )
                    heartbeat_list.append("\n⭕ No wallets info available")

            # Compose le message complet
            message_html = (
                "💓 <b>Heartbeat message:</b>\n\n"
                + "\n".join(heartbeat_list)
                + f"\n⏳ Heartbeat schedule: every <b>{app_config['service']['heartbeat_period_hours']}</b> hour(s)"
            )

            await send_alert(
                alert_type="heartbeat",
                level="info",
                html=message_html,
                disable_web_page_preview=True
            )

    except BaseException as E:
        logger.error(f"[HEARTBEAT] Exception {str(E)} ({E})")
    finally:
        logger.error(f"[HEARTBEAT] <- Quit heartbeat")

    return

if __name__ == "__main__":
    pass
