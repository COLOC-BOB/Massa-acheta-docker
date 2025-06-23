# massa_acheta_docker/telegram/dispatch.py
from aiogram.fsm.context import FSMContext
from telegram.handlers.view_config import cmd_view_config
from telegram.handlers.view_node import cmd_view_node
from telegram.handlers.view_wallet import cmd_view_wallet
from telegram.handlers.chart_wallet import cmd_chart_wallet
from telegram.handlers.view_address import cmd_view_address
from telegram.handlers.view_credits import cmd_view_credits
from telegram.handlers.view_earnings import cmd_view_earnings
from telegram.handlers.add_node import cmd_add_node
from telegram.handlers.add_wallet import cmd_add_wallet
from telegram.handlers.delete_node import cmd_delete_node
from telegram.handlers.delete_wallet import cmd_delete_wallet
from telegram.handlers.massa_info import cmd_massa_info
from telegram.handlers.massa_chart import cmd_massa_chart
from telegram.handlers.acheta_release import cmd_acheta_release
from telegram.handlers.view_id import cmd_view_id
from telegram.handlers.cancel import cmd_cancel
from telegram.handlers.reset import cmd_reset
from telegram.handlers.unknown import cmd_unknown
from telegram.handlers.help import cmd_help
from telegram.handlers.watchers_menu import cmd_watchers_menu

async def dispatch_command(cmd: str, msg, state: FSMContext):
    if cmd == "/help":
        await cmd_help(msg, state)
    elif cmd == "/view_config":
        await cmd_view_config(msg, state)
    elif cmd == "/view_node":
        await cmd_view_node(msg, state)
    elif cmd == "/view_wallet":
        await cmd_view_wallet(msg, state)
    elif cmd == "/chart_wallet":
        await cmd_chart_wallet(msg, state)
    elif cmd == "/view_address":
        await cmd_view_address(msg, state)
    elif cmd == "/view_credits":
        await cmd_view_credits(msg, state) 
    elif cmd == "/view_earnings":
        await cmd_view_earnings(msg, state)
    elif cmd == "/add_node":
        await cmd_add_node(msg, state)
    elif cmd == "/add_wallet":
        await cmd_add_wallet(msg, state) 
    elif cmd == "/delete_node":
        await cmd_delete_node(msg, state)
    elif cmd == "/delete_wallet":
        await cmd_delete_wallet(msg, state)
    elif cmd == "/massa_info":
        await cmd_massa_info(msg, state) 
    elif cmd == "/massa_chart":
        await cmd_massa_chart(msg, state)
    elif cmd == "/acheta_release":
        await cmd_acheta_release(msg, state)
    elif cmd == "/view_id":
        await cmd_view_id(msg, state)
    elif cmd == "/watchers":
        await cmd_watchers_menu(msg, state)
    elif cmd == "/cancel":
        await cmd_cancel(msg, state)
    elif cmd == "/reset":
        await cmd_reset(msg, state)
    elif cmd == "/unknown":
        await cmd_unknown(msg, state)
    else:
        await msg.answer("Commande reconnue, mais pas encore prise en charge.")
