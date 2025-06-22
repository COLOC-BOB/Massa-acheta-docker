# massa_acheta_docker/watchers/blocks.py

import asyncio
from loguru import logger

from watcher_utils import load_json_watcher, save_json_watcher
from remotes_utils import pull_http_api
import app_globals
from alert_manager import send_alert

WATCH_FILE = "watchers_state/blocks_seen.json"

def log_short_blocks(wallet_address, blocks, label="created_blocks", preview=10):
    n = len(blocks)
    if n == 0:
        logger.debug(f"{wallet_address} {label}: [aucun block]")
    else:
        short_list = blocks[:preview] + (["..."] if n > preview else [])
        logger.debug(f"{wallet_address} {label} (total {n}): {short_list}")

def format_block_info(block_data):
    header = block_data['content']['block']['header']['content']
    block_id = block_data['id']
    slot = header.get('slot', {})
    ops_count = len(block_data['content']['block'].get('operations', []))
    explorer_url = f"https://explorer.massa.net/mainnet/block/{block_id}"
    # Pas de preview, juste l’URL "plate"
    return (
        f"✅ <b>Nouveau block produit</b>\n"
        f"🔹 Block: <code>{block_id}</code>\n"
        f"🔹 Slot: thread {slot.get('thread', '?')} / period {slot.get('period', '?')}\n"
        f"🔹 Opérations dans le block: {ops_count}\n"
        f"🔹 Voir dans l'explorer: {explorer_url}"
    )

async def get_block_info(block_id, api_url):
    try:
        payload = {
            "jsonrpc": "2.0",
            "method": "get_blocks",
            "params": [[block_id]],
            "id": 0
        }
        resp = await pull_http_api(
            api_url=api_url,
            api_method="POST",
            api_payload=payload,
            api_content_type="application/json"
        )
        block_list = None
        if "result" in resp and isinstance(resp["result"], dict) and "result" in resp["result"]:
            block_list = resp["result"]["result"]
        elif "result" in resp and isinstance(resp["result"], list):
            block_list = resp["result"]
        else:
            block_list = []
        if block_list:
            return block_list[0]
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du block {block_id}: {e}")
    return None

async def fetch_and_alert_block(block_id, node_url, node_name, wallet_address):
    block_data = await get_block_info(block_id, node_url)
    if block_data:
        message = format_block_info(block_data)
        await send_alert(
            alert_type="watcher_block_produced",
            node=node_name,
            wallet=wallet_address,
            level="info",
            html=message,
            disable_web_page_preview=True
        )
        logger.success(f"🟢 Nouveau block créé par {wallet_address}: {block_id}")
    else:
        logger.warning(f"Block {block_id} non trouvé ou non récupéré par l'API.")

async def watch_blocks(polling_interval=10):
    try:
        previous_blocks = load_json_watcher(WATCH_FILE, {})
    except Exception as e:
        logger.error(f"Erreur chargement {WATCH_FILE} : {e}")
        previous_blocks = {}

    logger.info("Watcher: blocks started")
    while True:
        for node_name, node_data in app_globals.app_results.items():
            node_url = node_data.get("url")
            for wallet_address in node_data.get("wallets", {}):
                logger.debug(f"Checking wallet {wallet_address} on node {node_name}")
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
                    logger.warning(f"API error for {wallet_address}@{node_name}: {e}")
                    continue

                result = resp.get("result", {}).get("result")

                if not result or not isinstance(result, list) or not result[0]:
                    logger.debug(f"{wallet_address}: résultat API inexploitable")
                    continue
                if "created_blocks" not in result[0]:
                    logger.debug(f"{wallet_address}: champ 'created_blocks' absent dans la réponse")
                    continue
                created_blocks = result[0]["created_blocks"]
                log_short_blocks(wallet_address, created_blocks, label="created_blocks")

                old_blocks = previous_blocks.get(wallet_address, [])
                log_short_blocks(wallet_address, old_blocks, label="old_blocks")

                new_blocks = [b for b in created_blocks if b not in old_blocks]
                log_short_blocks(wallet_address, new_blocks, label="new_blocks")

                if not created_blocks or len(created_blocks) == 0:
                    logger.warning(f"{wallet_address}@{node_name}: Pas de blocks créés (created_blocks vide). Peut-être une limitation du node public.")
                    continue

                if new_blocks:
                    for block_id in new_blocks:
                        asyncio.create_task(
                            fetch_and_alert_block(block_id, node_url, node_name, wallet_address)
                        )
                    previous_blocks[wallet_address] = created_blocks
                    try:
                        save_json_watcher(WATCH_FILE, previous_blocks)
                        logger.info(f"{WATCH_FILE} mis à jour pour {wallet_address} ({len(created_blocks)} blocks connus)")
                    except Exception as e:
                        logger.error(f"Erreur sauvegarde {WATCH_FILE}: {e}")
        await asyncio.sleep(polling_interval)
