from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from watchers.watchers_control import load_watchers_config, set_watcher_state
from aiogram.fsm.context import FSMContext

router = Router()

def build_watchers_kb():
    config = load_watchers_config()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{name} : {'✅' if enabled else '❌'}",
                    callback_data=f"toggle_watcher_{name}"
                )
            ]
            for name, enabled in config.items()
        ]
    )

async def cmd_watchers_menu(message: types.Message, state: FSMContext):
    await show_watchers_menu(message)


@router.message(F.text == "/watchers")
async def show_watchers_menu(message: types.Message):
    kb = build_watchers_kb()
    await message.answer("👀 <b>Active watchers:</b>\nTap to enable/disable.", reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("toggle_watcher_"))
async def toggle_watcher(query: types.CallbackQuery):
    watcher_name = query.data.replace("toggle_watcher_", "")
    config = load_watchers_config()
    new_state = not config.get(watcher_name, True)
    set_watcher_state(watcher_name, new_state)
    await query.answer(f"{watcher_name} {'enabled' if new_state else 'disabled'}")
    # Refresh the menu
    kb = build_watchers_kb()
    await query.message.edit_reply_markup(reply_markup=kb)
