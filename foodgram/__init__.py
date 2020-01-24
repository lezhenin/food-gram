import logging

from aiogram import Bot
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

from .extensions.filters import OrderOwnerFilter, UserStateFilter, ChatStateFilter, ChatTypeFilter
from .extensions.firebase import FirebaseStorage

from .config import BOT_API_TOKEN, FIREBASE_CREDENTIALS_FILE

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=BOT_API_TOKEN)
bot.parse_mode = 'HTML'

db_storage = FirebaseStorage(FIREBASE_CREDENTIALS_FILE)
storage = db_storage

dp = Dispatcher(bot, storage=storage)

dp.filters_factory.bind(OrderOwnerFilter)
dp.filters_factory.bind(UserStateFilter)
dp.filters_factory.bind(ChatStateFilter)
dp.filters_factory.bind(ChatTypeFilter)

from . import handlers


def run_bot():
    executor.start_polling(dp, skip_updates=True)
