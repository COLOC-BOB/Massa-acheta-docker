from aiogram.types import BotCommand
from aiogram.utils.formatting import as_list, as_line, TextLink

# Tuples of (command, description) for the private bot mode
PRIVATE_COMMANDS: list[tuple[str, str]] = [
    ("/help", "Show help info"),
    ("/view_config", "View service config"),
    ("/view_node", "View node status"),
    ("/view_wallet", "View wallet info"),
    ("/chart_wallet", "View wallet chart"),
    ("/view_address", "View any wallet info"),
    ("/clean_address", "Clean remembered address"),
    ("/view_credits", "View any wallet credits"),
    ("/view_earnings", "View rewards for staking"),
    ("/add_node", "Add node to bot"),
    ("/add_wallet", "Add wallet to bot"),
    ("/delete_node", "Delete node from bot"),
    ("/delete_wallet", "Delete wallet from bot"),
    ("/massa_info", "Show MASSA network info"),
    ("/massa_chart", "Show MASSA network chart"),
    ("/acheta_release", "Actual Acheta release"),
    ("/view_id", "Show your TG ID"),
    ("/cancel", "Cancel ongoing scenario"),
    ("/reset", "Reset bot configuration"),
]

# Tuples of (command, description) for the public bot mode
PUBLIC_COMMANDS: list[tuple[str, str]] = [
    ("/help", "Show help info"),
    ("/view_address", "View any wallet info"),
    ("/clean_address", "Clean remembered address"),
    ("/view_credits", "View any wallet credits"),
    ("/view_earnings", "View rewards for staking"),
    ("/massa_info", "Show MASSA network info"),
    ("/massa_chart", "Show MASSA network chart"),
    ("/view_id", "Show your TG ID"),
    ("/cancel", "Cancel ongoing scenario"),
]

def get_bot_commands(public: bool) -> list[BotCommand]:
    """Return list of BotCommand objects for the current mode."""
    commands = PUBLIC_COMMANDS if public else PRIVATE_COMMANDS
    return [BotCommand(command=cmd, description=desc) for cmd, desc in commands]

def build_help_text(public: bool) -> str:
    """Build help message text in HTML format."""
    commands = PUBLIC_COMMANDS if public else PRIVATE_COMMANDS
    lines: list[str | object] = ["📖 Commands:", "⦙", "⦙… /start or /help : Show help info", "⦙"]
    for cmd, desc in commands:
        if cmd == "/help":
            continue
        lines.append(f"⦙… {cmd} : {desc}")
        lines.append("⦙")
    lines.extend([
        as_line("👉 ", TextLink("More info here", url="https://github.com/dex2code/massa_acheta/")),
        as_line("🎁 Wanna thank the author? ", TextLink("Ask me how", url="https://github.com/dex2code/massa_acheta#thank-you")),
    ])
    return as_list(*lines).as_html()
