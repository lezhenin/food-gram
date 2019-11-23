import logging

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor

from orderinfo import OrderInfo
import photo_proc

logging.basicConfig(level=logging.DEBUG)

# токен  бота
API_TOKEN = '1056772125:AAFQrxSVgSzMO3Ihc9Rb3n4Uqm9pYZAa5NQ'
# создание бота и диспетчера
bot = Bot(token=API_TOKEN)
bot.parse_mode = 'HTML'

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class OrderState(StatesGroup):
    idle = State()
    gather_places = State()
    poll = State()


@dp.message_handler(commands=['start'])
async def if_start(message: types.Message):

    if message.chat.type == 'private':
        message_text = "%s, привет. " \
                       "Команда /help поможет разобраться как что работает" % message.from_user.first_name
        await bot.send_message(message.chat.id, message_text)
        return

    current_state = await storage.get_state(chat=message.chat.id)
    if current_state is not None and current_state != OrderState.idle.state:
        return

    order_info = OrderInfo.from_message(message)
    await storage.set_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order_info)})
    await storage.set_state(chat=message.chat.id, state=OrderState.gather_places.state)

    message_text = "Привет, будем заказывать\n" \
                   "<b>%s</b> - инициатор заказа, будет иметь основные права и обязанности. " \
                   "Пишите места командой" % message.from_user.first_name
    await bot.send_message(message.chat.id, message_text)

    # информируем главного что он главный
    # message_text = "Привет, %s! Ты решил сделать заказ в чате %s \n 😎 " \
    #                % (message.from_user.first_name, message.chat.title)
    # await bot.send_message(message.from_user.id, message_text)


@dp.message_handler(commands=['addPlace'])
async def if_add_place(message: types.Message):
    # todo make filter for chat state
    current_state = await storage.get_state(chat=message.chat.id)
    if current_state != OrderState.gather_places.state:
        return

    parts = message.text.split(' ', maxsplit=1)
    if len(parts) < 2:
        return

    new_place = parts[1]
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    order.add_place(new_place)

    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})

    message_text = f"Место \"{new_place}\" было добавлено. Места участвующие в голосовании: {', '.join(order.places)}."
    await bot.send_message(message.chat.id, message_text)


@dp.message_handler(commands=['startPoll'])
async def if_start_poll(message: types.Message):
    # todo make filter for chat state
    current_state = await storage.get_state(chat=message.chat.id)
    if current_state != OrderState.gather_places.state:
        return

    # todo make filter for owner
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    if order.owner_user_id != message.from_user.id:
        return

    await storage.set_state(chat=message.chat.id, state=OrderState.poll.state)

    question = "Из какого места заказать еду?"
    sent_message = await bot.send_poll(message.chat.id, question, order.places, None, None)

    await storage.update_data(chat=message.chat.id, data={'poll_message_id': sent_message.message_id})


@dp.message_handler(commands=['showPlace'])
async def if_show_place(message: types.Message):

    current_state = await storage.get_state(chat=message.chat.id)
    if current_state != OrderState.poll.state:
        return

    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    if order.owner_user_id != message.from_user.id:
        return

    poll_message_id = data['poll_message_id']
    poll = await bot.stop_poll(message.chat.id, poll_message_id)

    poll.options.sort(key=lambda o: o.voter_count)
    winner_option = poll.options[0]

    message_text = f"Вариант \"{winner_option.text}\" набраил наибольшее количество голосов."
    await bot.send_message(message.chat.id, message_text)


@dp.message_handler(commands='cancel')
async def if_cancel(message: types.Message):
    current_state = await storage.get_state(chat=message.chat.id)
    if current_state is None or current_state == OrderState.idle.state:
        return

    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    if order.owner_user_id != message.from_user.id:
        return

    await storage.reset_state(chat=message.chat.id, with_data=True)

    message_text = "Текущий заказ отменен."
    await bot.send_message(message.chat.id, message_text)

# # обработчик команды /eat & /bill
# @dp.message_handler(content_types=['text'])
# async def if_message(message: types.Message):
#     global order_chats
#     global order_enable
#     global photo_enable
#
#     # командой eat разрешаем ввод заказа текстом
#     if message.text == '/eat':
#         # проверка что пользователь регистрировался в чате - жал makeorder
#         for i in order_chats:
#             if message.from_user.id in order_chats[i]:
#                 order_enable = 1
#                 await bot.send_message(message.from_user.id, 'Пиши пункты заказа через перенос')
#                 return
#         # если не нашли пользователя в массиве
#         await bot.send_message(message.from_user.id, "Вас нет в списках! Жмите makeorder в чате заказа")
#         return
#
#     # командой bill разрешаем отправку фото
#     elif message.text == '/bill':
#         photo_enable = 1
#         await bot.send_message(message.from_user.id, 'Отправь фото чека\nФото должно быть четким')
#
#         # если просто текст поступил с разрешенным txt_enable
#     else:
#         if order_enable:
#             order_enable = 0
#             tmp = 0
#             for i in order_chats:
#                 if message.from_user.id in order_chats[i]:
#                     tmp = i
#                     break
#             for i in range(len(message.text.split())):
#                 order_chats[tmp][message.from_user.id][i] = message.text.split()[i]
#             to_out = []
#             for i in order_chats[tmp][message.from_user.id]:
#                 to_out.append('<b>' + str(i) + '</b> - ' + str(order_chats[tmp][message.from_user.id][i]))
#             await bot.send_message(message.from_user.id, "\n".join(to_out))
#         else:
#             await bot.send_message(message.from_user.id, "/help  ⬅  жми")


@dp.message_handler(content_types=['photo'])
async def handle_docs_photo(message):
    photo_enable = False  # TODO handle current state
    if photo_enable:
        try:
            await photo_proc.qr_decode(message, bot, API_TOKEN)
        except Exception as e:
            await bot.send_message(message.chat.id, e)
    else:
        await bot.send_message(message.chat.id, 'К чему ты это?', reply_to_message_id=message)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
