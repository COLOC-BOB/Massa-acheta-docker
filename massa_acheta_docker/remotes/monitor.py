from loguru import logger
import asyncio

from app_config import app_config
import app_globals

from remotes.massa import massa_get_info
from remotes.node import check_node
from remotes.wallet import check_wallet
from remotes.releases import check_releases
from remotes_utils import save_app_results

from alert_manager import send_alert
from remotes.node import format_html_message

@logger.catch
async def monitor() -> None:
    logger.debug("-> Monitor")
    try:
        while True:
            # 1. Rafraîchir le statut réseau AVANT tout le reste !
            await massa_get_info()    # Ou await massa_get_status(), ou les deux selon ta logique

            node_coros = []
            wallet_coros = []

            # 2. Création des coroutines
            for node_name in app_globals.app_results:
                node_coros.append(check_node(node_name=node_name))
                for wallet_address in app_globals.app_results[node_name]['wallets']:
                    wallet_coros.append(check_wallet(node_name=node_name, wallet_address=wallet_address))

            # 3. Exécution des vérifications avec tolérance aux erreurs
            async with app_globals.results_lock:
                node_results = await asyncio.gather(*node_coros, return_exceptions=True)
                wallet_results = await asyncio.gather(*wallet_coros, return_exceptions=True)
                save_app_results()

            # 4. Log erreurs individuelles (nodes et wallets)
            for idx, result in enumerate(node_results):
                if isinstance(result, Exception):
                    logger.warning(f"Node check error (#{idx}): {result}")
            for idx, result in enumerate(wallet_results):
                if isinstance(result, Exception):
                    logger.warning(f"Wallet check error (#{idx}): {result}")

            # 5. Vérification releases
            await check_releases()

            # 6. Log et alerte si besoin
            nb_nodes = len(node_coros)
            nb_wallets = len(wallet_coros)
            logger.info(f"Monitor: {nb_nodes} nodes, {nb_wallets} wallets checked.")

            all_nodes_offline = all(
                not app_globals.app_results[n]['last_status']
                for n in app_globals.app_results
            )
            if all_nodes_offline and nb_nodes > 0:                
                await send_alert(
                    alert_type="all_nodes_offline",
                    level="critical",
                    details ="🚨 TOUS les nodes surveillés sont OFFLINE ! Vérifiez votre infrastructure.",
                    disable_web_page_preview=True,
                )


            logger.info(f"Sleeping for {app_config['service']['main_loop_period_min']} minutes...")
            await asyncio.sleep(app_config['service']['main_loop_period_min'] * 60)

    except BaseException as E:
        logger.error(f"Exception {str(E)} ({E})")
    finally:
        logger.error("<- Quit Monitor")
    return


if __name__ == "__main__":
    pass
