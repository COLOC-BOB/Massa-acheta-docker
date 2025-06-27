# massa_acheta_docker/telegram/menu_utils.py
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# === 1. Liste des commandes et labels ===
PRIVATE_COMMANDS = [
    ("/help", "Show help info", "Help"),
    ("/view_config", "View service config", "Configuration"),
    ("/view_node", "View node status", "Node status"),
    ("/view_wallet", "View wallet info", "My wallet"),
    ("/chart_wallet", "View wallet chart", "Wallet chart"),
    ("/view_address", "View any wallet info", "Wallet info"),
    ("/view_credits", "View any wallet credits", "Wallet credits"),
    ("/view_earnings", "View rewards for staking", "Rewards"),
    ("/add_node", "Add node to bot", "Add node"),
    ("/add_wallet", "Add wallet to bot", "Add wallet"),
    ("/delete_node", "Delete node from bot", "Delete node"),
    ("/delete_wallet", "Delete wallet from bot", "Delete wallet"),
    ("/massa_info", "Show MASSA network info", "MASSA info"),
    ("/massa_chart", "Show MASSA network chart", "MASSA chart"),
    ("/acheta_release", "Actual Acheta release", "Acheta release"),
    ("/view_id", "Show your TG ID", "My ID"),
    ("/watchers", "Show watchers menu", "Watchers"),
    ("/cancel", "Cancel ongoing scenario", "Cancel"),
    ("/reset", "Reset bot configuration", "Reset"),
]

# === 2. Mapping label -> commande ===
LABEL_TO_COMMAND = {label: cmd for cmd, _, label in PRIVATE_COMMANDS}

# === 3. Génération du clavier ===
def build_menu_keyboard() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    for _, _, label in PRIVATE_COMMANDS:
        kb.button(text=label)
    kb.adjust(3)  # 3 boutons par ligne
    return kb.as_markup(resize_keyboard=True, is_persistent=True)