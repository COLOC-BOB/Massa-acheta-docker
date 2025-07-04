# massa_acheta_docker/app_globals.py
from loguru import logger
import json
import asyncio
from pathlib import Path
from sys import exit as sys_exit
from collections import deque
from time import time
from dotenv import load_dotenv
import os
import requests

from app_config import app_config
from remotes_utils import save_app_results

# Charge les variables d'environnement .env (clé bot, chat id)
load_dotenv()

# --- Start time ---
acheta_start_time = int(time())

# --- Global mutex ---
results_lock = asyncio.Lock()

# --- Init results ---
app_results = {}

tg_bot = None
tg_dp = None

app_results_obj = Path(app_config['service']['results_path'])
if app_results_obj.exists():
    logger.info(f"[APP_GLOBALS] Loading results from '{app_results_obj}' file...")

    with open(file=app_results_obj, mode="rt") as input_results:
        try:
            app_results = json.load(fp=input_results)
        except BaseException as E:
            logger.critical(f"[APP_GLOBALS] Cannot load results from '{app_results_obj}' ({str(E)})")
            sys_exit(1)
        else:
            logger.info(f"[APP_GLOBALS] Successfully loaded results from '{app_results_obj}' file!")
else:
    logger.warning(f"[APP_GLOBALS] No results file '{app_results_obj}' exists. Trying to create...")

    try:
        if not save_app_results():
            raise Exception
    except BaseException as E:
        logger.critical(f"[APP_GLOBALS] Cannot create '{app_results_obj}' file. Exiting...")
        sys_exit(1)
    else:
        logger.info(f"[APP_GLOBALS] Successfully created empty '{app_results_obj}' file")

for node_name, node_data in app_results.items():
    node_data.setdefault('last_status', "unknown")
    node_data.setdefault('last_update', 0)
    node_data.setdefault('start_time', 0)
    node_data.setdefault('last_chain_id', 0)
    node_data.setdefault('last_cycle', 0)
    node_data.setdefault('last_result', {"unknown": "Never updated before"})

    for wallet_address, wallet_data in node_data.get('wallets', {}).items():
        wallet_data.setdefault('last_status', "unknown")
        wallet_data.setdefault('last_update', 0)
        wallet_data.setdefault('final_balance', 0)
        wallet_data.setdefault('candidate_rolls', 0)
        wallet_data.setdefault('active_rolls', 0)
        wallet_data.setdefault('missed_blocks', 0)
        wallet_data.setdefault('last_cycle', 0)
        wallet_data.setdefault('last_ok_count', 0)
        wallet_data.setdefault('last_nok_count', 0)
        wallet_data.setdefault('produced_blocks', 0)
        wallet_data.setdefault('last_result', {"unknown": "Never updated before"})
        if 'stat' not in wallet_data or not isinstance(wallet_data['stat'], deque):
            wallet_data['stat'] = deque(
                maxlen=int(24 * 60 / app_config['service']['main_loop_period_min'])
            )

# --- MASSA network values ---
massa_config = {}
massa_network = {}
massa_network['values'] = {
    "latest_release": "",
    "current_release": "",
    "current_cycle": 0,
    "roll_price": 0,
    "block_reward": 0,
    "total_stakers": 0,
    "total_staked_rolls": 0,
    "start_time": "",
    "node_id": "",
    "node_ip": "",
    "last_updated": 0
}
massa_network['stat'] = deque(
    maxlen=int(24 * 60 / app_config['service']['massa_network_update_period_min'])
)

# --- Restore stat values ---
app_stat_obj = Path(app_config['service']['stat_path'])
if app_stat_obj.exists():
    logger.info(f"[APP_GLOBALS] Loading stat from '{app_stat_obj}' file...")
    try:
        with open(file=app_stat_obj, mode="rt") as input_stat:
            app_stat = json.load(fp=input_stat)
    except BaseException as E:
        logger.error(f"[APP_GLOBALS] Cannot load stat from '{app_stat_obj}': ({str(E)})")
    else:
        logger.info(f"[APP_GLOBALS] Loaded app_stat from '{app_stat_obj}' successfully")
        try:
            for node_name in app_results:
                for wallet_address in app_results[node_name]['wallets']:
                    wallet_stat = app_stat['app_results'][node_name][wallet_address].get("stat", None)
                    if wallet_stat and type(wallet_stat) == list and len(wallet_stat) > 0:
                        for measure in wallet_stat:
                            app_results[node_name]['wallets'][wallet_address]['stat'].append(measure)
                    logger.info(f"[APP_GLOBALS] Restored {len(app_results[node_name]['wallets'][wallet_address]['stat'])} measures for wallet '{wallet_address}'@'{node_name}'")
        except BaseException as E:
            logger.error(f"[APP_GLOBALS] Cannot restore app_result stat ({str(E)})")
        else:
            logger.info(f"[APP_GLOBALS] Restored app_results stat successfully")
        try:
            massa_network_stat = app_stat['massa_network'].get("stat", None)
            if massa_network_stat and type(massa_network_stat) == list and len(massa_network_stat) > 0:
                for measure in massa_network_stat:
                    if type(measure) == dict:
                        massa_network['stat'].append(measure)
            logger.info(f"[APP_GLOBALS] Restored {len(massa_network['stat'])} measures for massa_network")
        except BaseException as E:
            logger.error(f"[APP_GLOBALS] Cannot restore massa_network stat ({str(E)})")
        else:
            logger.info(f"[APP_GLOBALS] Restored massa_network stat successfully")

# --- Telegram bot configuration (pour usage privé) ---
ACHETA_KEY = os.getenv("ACHETA_KEY")  # Placer ta clé dans .env
ACHETA_CHAT = int(os.getenv("ACHETA_CHAT"))  # ID du chat à surveiller (groupe, channel, ou chat privé)

# --- Telegram queue as simple deque (utilisé par le module alert_manager) ---
telegram_queue = deque()

# --- Acheta releases info (local, remote) ---
def fetch_latest_github_release():
    url = "https://api.github.com/repos/COLOC-BOB/Massa-acheta-docker/releases/latest"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("tag_name", "")
    except Exception as e:
        logger.warning(f"[APP_GLOBALS] Could not fetch latest GitHub release: {str(e)}")
        return ""
    
local_acheta_release = "v2.0.0"
latest_acheta_release = fetch_latest_github_release()

# --- Init deferred_credits ---
deferred_credits = {}
deferred_credits_obj = Path(app_config['service']['deferred_credits_path'])
if not deferred_credits_obj.exists():
    logger.warning(f"[APP_GLOBALS] No deferred_credits file '{deferred_credits_obj}' exists. Skipping...")
    with open(file=deferred_credits_obj, mode="rt") as input_deferred_credits:
        try:
            deferred_credits = json.load(fp=input_deferred_credits)
        except BaseException as E:
            logger.error(f"[APP_GLOBALS] Cannot load deferred_credits from '{deferred_credits_obj}' ({str(E)})")
        else:
            logger.info(f"[APP_GLOBALS] Successfully loaded deferred_credits from '{deferred_credits_obj}' file!")

if __name__ == "__main__":
    pass
