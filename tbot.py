# мпорт библиотек
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

import requests
import random

# токен  бота
API_TOKEN = '1056772125:AAFQrxSVgSzMO3Ihc9Rb3n4Uqm9pYZAa5NQ'

# предопределенные места заказа
def_place = ['McDonald’s', 'Burger King', 'KFC', 'SubWay', 'Теремок', 'DelMar', 'Две палочки', 'Шоколадница']

# создание бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

firebase_admin.initialize_app(
    credentials.Certificate('credentials.json')
)
db = firestore.client()


def get_id():  # для получения id чата
    MethodGetUpdates = 'https://api.telegram.org/bot{token}/getUpdates'.format(token=API_TOKEN)
    response = requests.post(MethodGetUpdates)
    results = response.json()
    return results['result'][0]['message']['chat']['id']


# обработик команды /start
@dp.message_handler(commands=['start'])
async def if_start(message: types.Message):
    some_data = {'event': 'send_start_message', 'user_id': message.from_user.id, 'message_id': message.message_id}
    db.collection('events').add(some_data)
    await bot.send_message(get_id(), "Привет!\nПомогу тебе и твоей группе упростить процесс заказа.")


# обработик команды /help
@dp.message_handler(commands=['help'])
async def if_help(message: types.Message):
    await bot.send_message(get_id(), "Добавь меня в беседу. Там мы определимся с местом и составом заказа")


# обработик команды /showplace
@dp.message_handler(commands=['showplace'])
async def if_showplace(message: types.Message):
    caht_id = get_id()
    a ='\n'.join(def_place)
    await bot.send_message(caht_id, a)


@dp.message_handler(commands=['makeorder'])
async def if_showplace(message: types.Message):
    await bot.send_message(message.from_user.id, 'Заказывай')


# обработик текстовых сообщений
@dp.message_handler()
def echo_message(msg: types.Message):
    bot.send_message(msg.from_user.id, 'Не доступно')


#
if __name__ == '__main__':
    executor.start_polling(dp)
