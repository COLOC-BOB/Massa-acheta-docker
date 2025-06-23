# massa_acheta_docker/telegram/menu_utils.py
from aiogram.types import ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# === 1. Liste des commandes et labels ===
PRIVATE_COMMANDS = [
    ("/help", "Show help info", "Aide"),
    ("/view_config", "View service config", "Configuration"),
    ("/view_node", "View node status", "État du nœud"),
    ("/view_wallet", "View wallet info", "Mon wallet"),
    ("/chart_wallet", "View wallet chart", "Graphique wallet"),
    ("/view_address", "View any wallet info", "Infos wallet"),
    ("/view_credits", "View any wallet credits", "Crédits wallet"),
    ("/view_earnings", "View rewards for staking", "Récompenses"),
    ("/add_node", "Add node to bot", "Ajouter un nœud"),
    ("/add_wallet", "Add wallet to bot", "Ajouter un wallet"),
    ("/delete_node", "Delete node from bot", "Suppr. nœud"),
    ("/delete_wallet", "Delete wallet from bot", "Suppr. wallet"),
    ("/massa_info", "Show MASSA network info", "Infos MASSA"),
    ("/massa_chart", "Show MASSA network chart", "Graphique MASSA"),
    ("/acheta_release", "Actual Acheta release", "Version Acheta"),
    ("/view_id", "Show your TG ID", "Mon ID"),
    ("/cancel", "Cancel ongoing scenario", "Annuler"),
    ("/reset", "Reset bot configuration", "Réinitialiser"),
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