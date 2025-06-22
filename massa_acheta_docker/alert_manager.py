# massa_acheta_docker/alert_manager.py
import time
from datetime import datetime
from loguru import logger
from telegram.queue import queue_telegram_message
import app_globals

# Dictionnaire pour éviter le spam (alerte = clé unique, valeur = timestamp)
_alert_cooldown = {}

# Cooldown en secondes pour chaque type d'alerte
ALERT_DEFAULT_COOLDOWN = 300  # 5 minutes
ALERT_COOLDOWNS = {
    "node_offline": 180,
    "node_online": 180,       # 3 minutes entre 2 alertes offline
    "node_cycle_mismatch": 180,
    "wallet_balance_drop": 300,
    "wallet_roll_change": 300,
    "wallet_block_miss": 120,
    "wallet_block_produced": 5,
    "watcher_block_produced": 5,
    "release_update": 1800,     # 30 minutes
}

ALERT_LABELS = {
    "heartbeat": "💓 Heartbeat",
    "node_offline": "🔴 Node offline",
    "all_nodes_offline": "🔴 All nodes offline",
    "node_online": "🟢 Node online",
    "node_cycle_mismatch": "⏳ Cycle mismatch",
    "wallet_balance_drop": "💸 Wallet balance drop",
    "wallet_roll_change": "🔄 Wallet roll change",
    "wallet_block_miss": "❌ Block missed",
    "wallet_block_produced": "✅ Block produced",
    "watcher_block_produced": "✅ Block produced",
    "release_update": "⬆️ New release detected",
    # Ajoute d'autres types ici si besoin
}


def make_alert_key(alert_type, node=None, wallet=None, extra=None):
    key = f"{alert_type}:{node or ''}:{wallet or ''}:{extra or ''}"
    return key


def build_alert_message(alert_type, node=None, wallet=None, level="info", details=None):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    label = ALERT_LABELS.get(alert_type, "❗ Alert")

    node_str = ""
    if node:
        # Si c'est le nom du node (et pas un objet)
        node_name = node
        node_str = f"<b>Node:</b> <code>{node_name}</code>"
    wallet_str = ""
    if wallet:
        wallet_str = f"<b>Wallet:</b> <code>{wallet}</code>"

    details_str = f"\n<b>Details:</b> {details}" if details else ""
    message = (
        f"{label}\n"
        f"{node_str}{' | ' if node_str and wallet_str else ''}{wallet_str}\n"
        f"<b>Level:</b> {level}\n"
        f"<b>Time:</b> {ts}"
        f"{details_str}"
    )
    return message


async def send_alert(alert_type, node=None, wallet=None, level="info", details=None, html=None, extra=None, disable_web_page_preview=False):
    """
    Centralise l'envoi d'alertes, évite le spam, permet d'étendre à plusieurs canaux.
    - alert_type: ex: "node_offline", "wallet_block_miss", ...
    - node, wallet: noms éventuels pour la clé de spam
    - level: info/warning/critical
    - details: texte descriptif, ex: "Node unreachable"
    - html: texte html à envoyer (prioritaire si renseigné)
    """
    now = time.time()
    key = make_alert_key(alert_type, node, wallet, extra)

    # Cooldown personnalisé par type
    cooldown = ALERT_COOLDOWNS.get(alert_type, ALERT_DEFAULT_COOLDOWN)
    last_sent = _alert_cooldown.get(key, 0)
    if now - last_sent < cooldown:
        logger.info(
            f"Alert '{alert_type}' for {node or ''} {wallet or ''} skipped (cooldown)")
        return

    # Compose le message
    if html:
        message = html
    else:
        message = build_alert_message(
            alert_type=alert_type,
            node=node,
            wallet=wallet,
            level=level,
            details=details
        )

    # Récupère le label pour le logging
    label = ALERT_LABELS.get(alert_type, "❗ Alert")

    await queue_telegram_message(message_text=message, disable_web_page_preview=disable_web_page_preview)
    logger.debug(
        f"[ALERT] Type: {alert_type}, Label: {label}, Message: {message}")
    logger.info(
        f"Alert '{alert_type}' sent for {node or ''} {wallet or ''} (level: {level})")
    _alert_cooldown[key] = now

    # Ajoute ici d'autres canaux si tu veux (Discord, email, ...)
