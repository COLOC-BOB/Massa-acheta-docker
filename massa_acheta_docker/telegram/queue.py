# massa_acheta_docker/telegram/queue.py
from loguru import logger
import asyncio
from aiogram.enums import ParseMode

from app_config import app_config
import app_globals

@logger.catch
async def queue_telegram_message(chat_id=None, message_text: str = "", disable_web_page_preview: bool = False) -> bool:
    logger.debug("-> queue_telegram_message")

    if not chat_id:
        chat_id = app_globals.ACHETA_CHAT

    try:
        app_globals.telegram_queue.append({
            "chat_id": chat_id,
            "message_text": message_text,
            "disable_web_page_preview": disable_web_page_preview
        })
    except Exception as e:
        logger.error(f"Cannot add telegram message to queue: ({str(e)})")
        return False
    else:
        logger.info(f"Successfully added telegram message to queue!")
        return True

@logger.catch
async def operate_telegram_queue() -> None:
    logger.debug("-> operate_telegram_queue")
    try:
        while True:
            await asyncio.sleep(app_config['telegram']['sending_delay_sec'])

            if not app_globals.telegram_queue:
                continue

            number_unsent_messages = len(app_globals.telegram_queue)
            logger.debug(f"Telegram: {number_unsent_messages} unsent message(s) in queue")

            message = app_globals.telegram_queue[0]
            chat_id = message['chat_id']
            message_text = message['message_text']

            try:
                await app_globals.tg_bot.send_message(
                    chat_id=chat_id,
                    text=message_text,
                    parse_mode=ParseMode.HTML,
                    request_timeout=app_config['telegram']['sending_timeout_sec'],
                    disable_web_page_preview=message['disable_web_page_preview']
                )
            except Exception as e:
                logger.error(f"Could not send telegram message to chat_id '{chat_id}': ({str(e)})")
            else:
                logger.info(f"Successfully sent message to chat_id '{chat_id}' ({number_unsent_messages - 1} unsent message(s) in queue)")
                app_globals.telegram_queue.popleft()

    except Exception as e:
        logger.error(f"Exception {str(e)} ({e})")
    finally:
        logger.error("<- Quit operate_telegram_queue")

    return

if __name__ == "__main__":
    pass
