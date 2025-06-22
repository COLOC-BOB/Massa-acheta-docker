# massa_acheta_docker/remotes_utils.py
from loguru import logger
import aiohttp
import json
from time import time
from pathlib import Path
import requests
import traceback

from app_config import app_config
import app_globals

@logger.catch
async def pull_http_api(api_url: str=None,
                        api_method: str="GET",
                        api_header: object={"Content-Type": "application/json"},
                        api_payload: object={},
                        api_content_type: str="application/json",
                        api_root_element: str=None,
                        api_session_timeout: int=app_config['service']['http_session_timeout_sec'],
                        api_probe_timeout: int=app_config['service']['http_probe_timeout_sec']) -> object:

    logger.debug(f"-> pull_http_api")

    api_session_timeout = aiohttp.ClientTimeout(total=api_session_timeout)
    api_probe_timeout = aiohttp.ClientTimeout(total=api_probe_timeout)

    api_response_text = "No response from remote HTTP API"
    api_response_obj = {"error": "No response from remote HTTP API"}

    try:
        async with aiohttp.ClientSession(timeout=api_session_timeout) as session:
            if api_method == "GET":
                async with session.get(url=api_url, headers=api_header, timeout=api_probe_timeout) as api_response:
                    if api_response.status != 200:
                        raise Exception(f"Remote HTTP API Error '{str(api_response.status)}'")
                    if api_response.content_type != api_content_type:
                        raise Exception(f"Remote HTTP API wrong content type '{str(api_response.content_type)}'")
                    api_response_text = await api_response.text()
            elif api_method == "POST":
              # payload : str (déjà json.dumps) ou dict (idéalement)
              if isinstance(api_payload, str):
                  post_args = dict(data=api_payload)
              else:
                  post_args = dict(json=api_payload)

              logger.debug(f"API POST to {api_url}: type={type(api_payload)}, payload={api_payload}")
              async with session.post(
                  url=api_url,
                  headers=api_header,
                  timeout=api_probe_timeout,
                  **post_args
              ) as api_response:
                    if api_response.status != 200:
                        raise Exception(f"Remote HTTP API Error '{str(api_response.status)}'")
                    if api_response.content_type != api_content_type:
                        raise Exception(f"Remote API wrong content type '{str(api_response.content_type)}'")
                    api_response_text = await api_response.text()
            else:
                raise Exception(f"Unknown HTTP API method '{api_method}'")

        if api_content_type == "application/json":
            api_response_obj = json.loads(s=api_response_text)
            if not api_root_element:
                api_result = {"result": api_response_obj}
            else:
                api_result_value = api_response_obj.get(api_root_element, None)
                if api_result_value is not None:
                    api_result = {"result": api_result_value}
                elif "error" in api_response_obj:
                    api_result = {"error": api_response_obj["error"]}
                else:
                    raise Exception(f"A mandatory key '{api_root_element}' missed in remote HTTP API response: {api_response_text}")
        else:
            api_result = {"result": api_response_text}

    except BaseException as E:
        logger.error(
            f"Exception in remote HTTP API request for URL '{api_url}': {repr(E)}\n"
            f"{traceback.format_exc()}"
        )
        api_result = {"error": f"{repr(E)} | {traceback.format_exc()}"}

    else:
        logger.info(f"Successfully pulled from remote HTTP API '{api_url}'")

    finally:
        return api_result

@logger.catch
def save_app_results() -> bool:
    logger.debug(f"-> save_app_results")

    composed_results = {}

    try:
        for node_name, node_data in app_globals.app_results.items():
            composed_results[node_name] = {}
            # Save node static and dynamic fields (except stats)
            for field in [
                "url",
                "last_status",
                "last_update",
                "start_time",
                "last_chain_id",
                "last_cycle",
                "last_result",
            ]:
                composed_results[node_name][field] = node_data.get(field, None)

            composed_results[node_name]["wallets"] = {}

            for wallet_address, wallet_data in node_data.get("wallets", {}).items():
                composed_results[node_name]["wallets"][wallet_address] = {}
                for w_field in [
                    "last_status",
                    "last_update",
                    "final_balance",
                    "candidate_rolls",
                    "active_rolls",
                    "missed_blocks",
                    "last_cycle",
                    "last_ok_count",
                    "last_nok_count",
                    "produced_blocks",
                    "last_result",
                ]:
                    composed_results[node_name]["wallets"][wallet_address][w_field] = wallet_data.get(
                        w_field, None
                    )

        app_results_obj = Path(app_config['service']['results_path'])
        with open(file=app_results_obj, mode="wt") as output_results:
            output_results.write(json.dumps(obj=composed_results, indent=4))
            output_results.flush()
                    
    except BaseException as E:
        logger.error(f"Cannot save app_results into '{app_results_obj}' file: ({str(E)})")
        return False
        
    else:
        logger.info(f"Successfully saved app_results into '{app_results_obj}' file!")
        return True

@logger.catch
def save_app_stat() -> bool:
    logger.debug(f"-> save_app_stat")

    composed_results = {
        "app_results": {},
        "massa_network": {
            "stat": []
        }
    }

    for node_name in app_globals.app_results:
        composed_results['app_results'][node_name] = {}

        for wallet_address in app_globals.app_results[node_name]['wallets']:
            composed_results['app_results'][node_name][wallet_address] = {
                "stat": []
            }

            for measure in app_globals.app_results[node_name]['wallets'][wallet_address]['stat']:
                composed_results['app_results'][node_name][wallet_address]['stat'].append(measure)

    for measure in app_globals.massa_network['stat']:
        composed_results['massa_network']['stat'].append(measure)

    try:
        app_stat_obj = Path(app_config['service']['stat_path'])
        with open(file=app_stat_obj, mode="wt") as output_stat:
            output_stat.write(json.dumps(obj=composed_results, indent=4))
            output_stat.flush()
                    
    except BaseException as E:
        logger.error(f"Cannot save app_stat into '{app_stat_obj}' file: ({str(E)})")
        return False
        
    else:
        logger.info(f"Successfully saved app_stat into '{app_stat_obj}' file!")
        return True

@logger.catch
async def t_now() -> int:
    logger.debug("-> t_now")
    return int(time())

@logger.catch
async def get_last_seen(last_time: int=0, show_days: bool=False) -> str:
    logger.debug("-> get_last_seen")
    if last_time == 0:
        return "Never"
    
    current_time = await t_now()
    diff_seconds = current_time - last_time

    if show_days:
        diff_days = diff_seconds // (24 * 60 * 60)
        diff_hours = (diff_seconds - (diff_days * 24 * 60 * 60)) // (60 * 60)
        diff_mins = (diff_seconds - (diff_days * 24 * 60 * 60) - (diff_hours * 60 * 60)) // 60
        result = f"{diff_days}d {diff_hours}h {diff_mins}m"
    else:
        diff_hours = diff_seconds // (60 * 60)
        diff_mins = (diff_seconds - (diff_hours * 60 * 60)) // 60
        result = f"{diff_hours}h {diff_mins}m"

    return f"{result} ago"

@logger.catch
async def get_duration(start_time: int=0, show_days: bool=False) -> str:
    logger.debug("-> get_duration")
    if start_time == 0:
        return "unknown"

    current_time = await t_now()
    diff_seconds = current_time - start_time

    if show_days:
        diff_days = diff_seconds // (24 * 60 * 60)
        diff_hours = (diff_seconds - (diff_days * 24 * 60 * 60)) // (60 * 60)
        diff_mins = (diff_seconds - (diff_days * 24 * 60 * 60) - (diff_hours * 60 * 60)) // 60
        result = f"{diff_days}d {diff_hours}h {diff_mins}m"
    else:
        diff_hours = diff_seconds // (60 * 60)
        diff_mins = (diff_seconds - (diff_hours * 60 * 60)) // 60
        result = f"{diff_hours}h {diff_mins}m"

    return result

@logger.catch
async def get_short_address(address: str="") -> str:
    logger.debug("-> get_short_address")
    if len(address) > 16:
        return f"{address[0:8]}...{address[-6:]}"
    else:
        return address

@logger.catch
async def get_rewards_mas_day(rolls_number=100, total_rolls=0):
    SEC_PER_DAY = 86_400
    t0_ms = app_globals.massa_network['values'].get("t0", None)
    threads_num = app_globals.massa_network['values'].get("thread_count", None)
    block_reward = app_globals.massa_network['values'].get('block_reward', None)

    if not t0_ms or not threads_num or not block_reward:
        logger.debug(f"Paramètre manquant: t0_ms={t0_ms}, threads_num={threads_num}, block_reward={block_reward}")
        return 0  # paramètres manquants

    t0_sec = int(t0_ms) / 1_000
    threads_num = int(threads_num)
    blocks_per_day = (SEC_PER_DAY / t0_sec) * threads_num

    if total_rolls == 0:
        total_rolls = app_globals.massa_network['values'].get('total_staked_rolls', 0)

    logger.debug(f"RÉSUMÉ CALCUL: rolls_number={rolls_number}, total_rolls={total_rolls}, block_reward={block_reward}, t0_sec={t0_sec}, threads_num={threads_num}, blocks_per_day={blocks_per_day}")

    if total_rolls == 0 or rolls_number == 0 or blocks_per_day == 0:
        my_reward = 0
    else:
        my_blocks = blocks_per_day * (rolls_number / total_rolls)
        my_reward = my_blocks * block_reward

    logger.debug(f"Récompense journalière estimée: {my_reward} MAS")
    return int(my_reward)




@logger.catch
async def get_rewards_blocks_cycle(rolls_number: int=0, total_rolls: int=0) -> float:
    logger.debug("-> get_rewards_blocks_cycle")

    threads_num = app_globals.massa_config.get("thread_count", None)
    if threads_num:
        try:
            threads_num = int(threads_num)
        except BaseException:
            threads_num = 0
    else:
        threads_num = 0

    periods_per_cycle = app_globals.massa_config.get("periods_per_cycle", None)
    if periods_per_cycle:
        try:
            blocks_per_cycle = int(periods_per_cycle) * threads_num
        except BaseException:
            periods_per_cycle = 0
            blocks_per_cycle = 0
    else:
        periods_per_cycle = 0
        blocks_per_cycle = 0
    
    try:
        if total_rolls == 0:
            total_rolls = app_globals.massa_network['values']['total_staked_rolls']

        if total_rolls == 0 or rolls_number == 0:
            my_blocks = 0.0
        else:
            my_contribution = total_rolls / rolls_number
            my_blocks = round(
                blocks_per_cycle / my_contribution,
                4
            )
    
    except BaseException as E:
        logger.error(f"Cannot compute 'rewards_blocks_cycle' ({str(E)})")
        my_blocks = 0.0

    return my_blocks

import requests

@logger.catch
def update_deferred_credits_from_node():
    """
    Récupère les crédits différés pour tous les wallets présents dans app_globals.app_results
    et sauvegarde deferred_credits.json au format attendu.
    """
    RPC_URL = app_config['service']['mainnet_rpc_url']  # ex : "http://127.0.0.1:33035"
    OUTPUT_PATH = app_config['service']['deferred_credits_path']  # ex : "deferred_credits.json"

    # Collecte toutes les adresses wallet du projet
    wallets = []
    for node_data in app_globals.app_results.values():
        if 'wallets' in node_data:
            wallets.extend(node_data['wallets'].keys())
    wallets = list(set(wallets))  # unicité

    all_credits = {}
    for addr in wallets:
        payload = {
            "jsonrpc": "2.0",
            "method": "get_addresses",
            "params": [[addr]],
            "id": 0
        }
        try:
            response = requests.post(RPC_URL, json=payload, timeout=5)
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                logger.error(f"Erreur RPC pour {addr}: {result['error']}")
                all_credits[addr] = []
            else:
                raw_credits = result['result'][0].get('deferred_credits', [])
                # Correction si le format est dict au lieu de liste (compatibilité Massa node)
                if isinstance(raw_credits, dict):
                    credits_list = []
                    for period, values in raw_credits.items():
                        for value in values:
                            credit = value.copy()
                            credit["period"] = period  # Ajout utile si nécessaire
                            credits_list.append(credit)
                    all_credits[addr] = credits_list
                else:
                    all_credits[addr] = raw_credits
        except Exception as e:
            logger.error(f"Exception pour {addr}: {e}")
            all_credits[addr] = []

    # Sauvegarde le fichier au format attendu
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(all_credits, f, indent=4)
        logger.info(f"✅ deferred_credits.json mis à jour avec {len(all_credits)} wallet(s) !")
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde du fichier {OUTPUT_PATH}: {e}")



if __name__ == "__main__":
    pass
