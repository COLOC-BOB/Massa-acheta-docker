# massa_acheta_docker/telegram/handlers/help.py
from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from loguru import logger

router = Router()

@router.message(StateFilter(None), Command("help"))
@logger.catch
async def cmd_help(message: Message, state: FSMContext):
    help_text = (
        "🤖 <b>MASSA Acheta Bot – Features Guide</b>\n\n"
        "All main features are available via the menu or the main screen:\n"
        "──────────────────────────────\n"
        "• <b>📈 MAS Network Chart</b>\n"
        "    <i>Display a global chart of the Massa mainnet (stakers, rolls, stats)</i>\n\n"
        "• <b>💼 Wallet Stats</b>\n"
        "    <i>View detailed stats and staking history for your wallet</i>\n\n"
        "• <b>🏦 View Credits</b>\n"
        "    <i>See your deferred credits (pending rewards)</i>\n\n"
        "• <b>🪙 Wallet Earnings</b>\n"
        "    <i>Show total earnings and staking rewards</i>\n\n"
        "• <b>🧩 Node Info</b>\n"
        "    <i>Display information about your configured nodes</i>\n\n"
        "• <b>🗃️ Node Config</b>\n"
        "    <i>Show current bot configuration (nodes, wallets)</i>\n\n"
        "• <b>➕ Add Node</b>\n"
        "    <i>Add a Massa node to monitor</i>\n\n"
        "• <b>➕ Add Wallet</b>\n"
        "    <i>Add a wallet address to track</i>\n\n"
        "• <b>🗑️ Delete Node</b>\n"
        "    <i>Remove a node from your configuration</i>\n\n"
        "• <b>🗑️ Delete Wallet</b>\n"
        "    <i>Remove a wallet from your configuration</i>\n\n"
        "• <b>🔎 Wallet Address</b>\n"
        "    <i>Display the selected wallet address</i>\n\n"
        "• <b>🧹 Clean Address</b>\n"
        "    <i>Remove invalid or unused addresses</i>\n\n"
        "• <b>🌐 Massa Network Info</b>\n"
        "    <i>Show live information from the Massa mainnet</i>\n\n"
        "• <b>📊 Mainnet Chart</b>\n"
        "    <i>Display mainnet evolution charts</i>\n\n"
        "• <b>⬆️ Latest Release</b>\n"
        "    <i>Check for the latest Acheta and Massa node versions</i>\n\n"
        "• <b>🆔 Your Telegram ID</b>\n"
        "    <i>Show your Telegram user ID (for support)</i>\n\n"
        "• <b>⚙️ Settings</b>\n"
        "    <i>Access bot settings and configuration</i>\n\n"
        "• <b>❌ Cancel</b>\n"
        "    <i>Cancel the current operation or menu</i>\n\n"
        "• <b>🔄 Reset</b>\n"
        "    <i>Reset the bot to its initial state</i>\n\n"
        "• <b>❓ Help</b>\n"
        "    <i>Show this help guide</i>\n"
        "──────────────────────────────\n"
        "<i>Tip: You can access each feature via the menu, the main screen, or with dedicated buttons.</i>"
    )


    await message.answer(
        help_text,
        parse_mode="HTML"
    )
