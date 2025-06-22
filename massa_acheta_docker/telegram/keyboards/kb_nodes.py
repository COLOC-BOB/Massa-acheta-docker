from loguru import logger
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

import app_globals

def kb_nodes() -> ReplyKeyboardMarkup:
    logger.debug("-> kb_nodes") 

    try:
        node_keyboard = ReplyKeyboardBuilder()

        if not app_globals.app_results:
            node_keyboard.button(text="No nodes found")
        else:
            for node_name in app_globals.app_results:
                node_keyboard.button(text=node_name)

        node_keyboard.adjust(2)
        return node_keyboard.as_markup(resize_keyboard=True)
    except Exception as e:
        logger.error(f"Cannot build node_keyboard: ({str(e)})")
        # Retourne un clavier minimaliste même en cas d’erreur
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="No nodes")]],
            resize_keyboard=True
        )
