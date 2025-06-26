# massa_acheta_docker/remotes/massa.py
from loguru import logger
import asyncio
import json

from app_config import app_config
import app_globals
from remotes_utils import pull_http_api, t_now, save_app_stat

@logger.catch
async def massa_get_info() -> bool:
    logger.debug(f"[MASSA] -> massa_get_info")
    try:
        massa_info_answer = await pull_http_api(
            api_url=f"{app_config['service']['mainnet_rpc_url']}/info",
            api_method="GET"
        )
        massa_info_result = massa_info_answer.get("result", None)
        if not massa_info_result:
            logger.warning(f"[MASSA] No result in MASSA mainnet RPC /info answer ({massa_info_answer})")
            return False

        # Champs principaux (ne pas inclure les champs non présents)
        for api_field, global_key in [
            ("version", "current_release"),
            ("n_stakers", "total_stakers"),
            ("current_cycle", "current_cycle"),
        ]:
            value = massa_info_result.get(api_field)
            if value is not None:
                app_globals.massa_network['values'][global_key] = value
            else:
                logger.warning(f"[MASSA] No {api_field} in MASSA mainnet RPC /info answer")

    except Exception as E:
        logger.warning(f"[MASSA] Cannot operate MASSA mainnet RPC /info: {E}")
        return False

    logger.debug(f"[MASSA] /info: {app_globals.massa_network['values']}")
    return True

@logger.catch
async def massa_get_status() -> bool:
    logger.debug(f"[MASSA] -> massa_get_status")
    payload = json.dumps({
        "id": 0,
        "jsonrpc": "2.0",
        "method": "get_status",
        "params": []
    })

    try:
        massa_status_answer = await pull_http_api(
            api_url=app_config['service']['mainnet_rpc_url'],
            api_method="POST",
            api_payload=payload,
            api_root_element="result"
        )
        massa_status_result = massa_status_answer.get("result", None)
        if not massa_status_result:
            logger.warning(f"[MASSA] No result in MASSA mainnet RPC 'get_status' answer ({massa_status_answer})")
            return False

        # Extraction des champs principaux
        for api_field, global_key in [
            ("node_id", "node_id"),
            ("node_ip", "node_ip"),
            ("version", "current_release"),
            ("current_cycle", "current_cycle"),
            ("chain_id", "chain_id"),
        ]:
            value = massa_status_result.get(api_field)
            if value is not None:
                app_globals.massa_network['values'][global_key] = value

        # Config réseau
        config = massa_status_result.get("config", {})
        if config:
            app_globals.massa_config = config.copy()
            logger.debug(f"[MASSA] massa_config updated: {app_globals.massa_config}")
        for api_field, global_key, cast in [
            ("block_reward", "block_reward", float),
            ("roll_price", "roll_price", int),
            ("thread_count", "thread_count", int),
            ("t0", "t0", int),
            ("periods_per_cycle", "periods_per_cycle", int)
        ]:
            value = config.get(api_field)
            if value is not None:
                try:
                    app_globals.massa_network['values'][global_key] = cast(value)
                except Exception:
                    app_globals.massa_network['values'][global_key] = value


        # Statistiques (optionnelles, non utilisées ici mais accessibles)
        for k in ["consensus_stats", "network_stats", "execution_stats"]:
            value = massa_status_result.get(k, {})
            if value:
                app_globals.massa_network['values'][k] = value

    except Exception as E:
        logger.warning(f"[MASSA] Cannot operate MASSA mainnet RPC get_status: {E}")
        return False

    logger.debug(f"[MASSA] massa_get_status: {app_globals.massa_network['values']}")
    return True

@logger.catch
async def massa_get_stakers() -> bool:
    logger.debug(f"[MASSA] -> massa_get_stakers")
    massa_total_rolls = 0
    massa_stakers_offset = 0
    massa_stakers_bundle_length = app_config['service']['mainnet_stakers_bundle']

    while True:
        logger.debug(f"[MASSA] massa_get_stakers loop offset {massa_stakers_offset}")
        payload = json.dumps({
            "id": 0,
            "jsonrpc": "2.0",
            "method": "get_stakers",
            "params": [{
                "limit": massa_stakers_bundle_length,
                "offset": massa_stakers_offset
            }]
        })
        try:
            massa_stakers_answer = await pull_http_api(
                api_url=app_config['service']['mainnet_rpc_url'],
                api_method="POST",
                api_payload=payload,
                api_root_element="result"
            )
            massa_stakers_result = massa_stakers_answer.get("result", None)
            # Cas erreur : pas de result
            if massa_stakers_result is None:
                logger.warning(f"[MASSA] No result in MASSA mainnet RPC 'get_stakers' answer ({massa_stakers_answer})")
                break
            # Cas résultat = dict vide : fin de pagination
            if isinstance(massa_stakers_result, dict):
                logger.info(f"[MASSA] End of stakers pagination (empty dict)")
                break
            # Cas résultat = liste vide
            if isinstance(massa_stakers_result, list) and len(massa_stakers_result) == 0:
                logger.info(f"[MASSA] No more stakers to fetch.")
                break
            # Cas résultat = liste
            if isinstance(massa_stakers_result, list):
                for staker in massa_stakers_result:
                    if isinstance(staker, (list, tuple)) and len(staker) == 2:
                        try:
                            massa_total_rolls += int(staker[1])
                        except Exception:
                            logger.warning(f"[MASSA] Invalid roll number for staker {staker}")
                    else:
                        logger.warning(f"[MASSA] Cannot take rolls number from staker '{staker}'")
                # Pagination : avancer du nombre reçu
                massa_stakers_offset += len(massa_stakers_result)
            else:
                logger.warning(f"[MASSA] Unknown format in MASSA mainnet RPC 'get_stakers' answer: {type(massa_stakers_result)}")
                break
        except BaseException as E:
            logger.warning(f"[MASSA] Cannot operate MASSA mainnet RPC get_stakers: {E}")
            return False

        await asyncio.sleep(1)

    app_globals.massa_network['values']['total_staked_rolls'] = massa_total_rolls
    logger.debug(f"[MASSA] massa_get_stakers: total_staked_rolls: {massa_total_rolls}")
    return True


@logger.catch
async def massa() -> None:
    logger.debug(f"[MASSA] -> massa")
    try:
        while True:
            success_flag = True
            if success_flag and await massa_get_info():
                logger.info(f"[MASSA] Successfully pulled /info from MASSA mainnet RPC")
                await asyncio.sleep(1)
            else:
                success_flag = False
                logger.warning(f"[MASSA] Error pulling /info from MASSA mainnet RPC")

            if success_flag and await massa_get_status():
                logger.info(f"[MASSA] Successfully pulled get_status from MASSA mainnet RPC")
                await asyncio.sleep(1)
            else:
                success_flag = False
                logger.warning(f"[MASSA] Error pulling get_status from MASSA mainnet RPC")

            if success_flag and await massa_get_stakers():
                logger.info(f"[MASSA] Successfully pulled get_stakers from MASSA mainnet RPC")
                await asyncio.sleep(1)
            else:
                success_flag = False
                logger.warning(f"[MASSA] Error pulling get_stakers from MASSA mainnet RPC")

            if success_flag:
                logger.info(f"[MASSA] Successfully collected MASSA mainnet network info")
                time_now = await t_now()
                try:
                    app_globals.massa_network['values']['last_updated'] = time_now
                    app_globals.massa_network['stat'].append(
                        {
                            "time": time_now,
                            "cycle": app_globals.massa_network['values'].get("current_cycle"),
                            "stakers": app_globals.massa_network['values'].get("total_stakers"),
                            "rolls": app_globals.massa_network['values'].get("total_staked_rolls"),
                            "release": app_globals.massa_network['values'].get("current_release"),
                            "block_reward": app_globals.massa_network['values'].get("block_reward"),
                            "roll_price": app_globals.massa_network['values'].get("roll_price"),
                            "node_id": app_globals.massa_network['values'].get("node_id"),
                            "ip": app_globals.massa_network['values'].get("node_ip"),
                        }
                    )
                except Exception as E:
                    logger.warning(f"[MASSA] Cannot store MASSA stat ({E})")
                else:
                    logger.info(f"[MASSA] Successfully stored MASSA stat ({len(app_globals.massa_network['stat'])} measures)")
            else:
                logger.warning(f"[MASSA] Could not collect MASSA mainnet network info")
            logger.info(f"[MASSA] Sleeping for {app_config['service']['massa_network_update_period_min'] * 60} seconds...")
            await asyncio.sleep(app_config['service']['massa_network_update_period_min'] * 60)
            save_app_stat()
    except Exception as E:
        logger.error(f"[MASSA] Exception {E}")
    finally:
        logger.error(f"[MASSA] <- Quit massa")
    return

if __name__ == "__main__":
    pass
