# massa_acheta_docker/telegram/menu.py
from aiogram.types import BotCommand, ReplyKeyboardMarkup, Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram import Router, F
from telegram.dispatch import dispatch_command
from telegram.menu_utils import build_menu_keyboard, PRIVATE_COMMANDS, LABEL_TO_COMMAND
from aiogram.fsm.context import FSMContext

# === 1. Génération des commandes Telegram (pour set_my_commands) ===
def get_bot_commands() -> list[BotCommand]:
    return [BotCommand(command=cmd, description=desc) for cmd, desc, _ in PRIVATE_COMMANDS]

# === 2. Texte du menu (pour /help ou /start) ===
def build_menu_text() -> str:
    lines = ["<b>📖 Commandes disponibles :</b>\n>"]
    lines.append("⦙\n>⦙… /start : Afficher le menu\n>⦙\n>")
    for cmd, desc, _ in PRIVATE_COMMANDS:
        if cmd == "/help":
            continue
        lines.append(f"⦙… {cmd} : {desc}\n>⦙\n>")
    lines.append(
        '👉 <a href="https://github.com/dex2code/massa_acheta/">Plus d\'infos ici</a>\n>'
        '🎁 Un merci à l\'auteur ? <a href="https://github.com/dex2code/massa_acheta#thank-you">Voir ici</a>'
    )
    return ''.join(lines)

# === 3. Router Aiogram v3 — à inclure dans ton main.py ===
router = Router()

@router.message(F.text)
async def handle_menu_label(msg: Message, state: FSMContext):
    label = msg.text.strip()
    if label in LABEL_TO_COMMAND:
        cmd = LABEL_TO_COMMAND[label]
        await dispatch_command(cmd, msg, state)   # <-- exécute le handler correspondant
    else:
        await msg.answer("Commande inconnue. Utilise le menu !", reply_markup=build_menu_keyboard())
  
  