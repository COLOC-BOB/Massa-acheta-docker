from loguru import logger
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder

import app_globals

def kb_wallets(node_name: str = "") -> ReplyKeyboardMarkup:
    logger.debug("-> kb_wallets")

    try:
        wallet_keyboard = ReplyKeyboardBuilder()
        if node_name not in app_globals.app_results or not app_globals.app_results[node_name]['wallets']:
            wallet_keyboard.button(text="No wallets found")
        else:
            for wallet_address in app_globals.app_results[node_name]['wallets']:
                wallet_keyboard.button(text=wallet_address)

        wallet_keyboard.adjust(1)
        return wallet_keyboard.as_markup(resize_keyboard=True)
    except Exception as e:
        logger.error(f"Cannot build wallet_keyboard: ({str(e)})")
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="No wallets")]],
            resize_keyboard=True
        )
