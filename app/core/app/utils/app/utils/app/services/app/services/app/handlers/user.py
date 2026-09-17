from aiogram import Router, types
from aiogram.filters import CommandStart
from app.utils.texts import WELCOME_TEXT
from app.utils.keyboards import main_menu
from app.core.config import SUPPORT_USERNAME

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        WELCOME_TEXT.format(support=SUPPORT_USERNAME),
        reply_markup=main_menu()
    )
