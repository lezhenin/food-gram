from io import BytesIO
from difflib import get_close_matches

from aiogram.types import Message

from .. import bot, dp, storage
from ..model.state import ChatState
from ..model.orderinfo import OrderInfo
from ..utils import bill

from foodgram.model.state import UserState


@dp.message_handler(content_types=['photo'], state='*', chat_state=[ChatState.waiting_order])
async def handle_docs_photo(message: Message):
    photos = message.photo
    if len(photos) < 1:
        return

    image_bytes = BytesIO()
    a = photos[0]
    for i in range(len(photos[1:len(photos)])):
        if a.file_size < photos[i].file_size:
            a = photos[i]
    await a.download(image_bytes)

    bills = await bill.decode_qr(image_bytes)
    if len(bills) < 1:
        await bot.send_message(message.chat.id, 'Невозможно декодировать QR код.')
        return

    await bot.send_message(message.chat.id, 'Выполняется поиск чека...')
    data = await bill.get_data(bills[0])
    if data is None:
        await bot.send_message(message.chat.id, 'Не удалось найти чек.')
        return
    items = data['document']['receipt']['items']

    num = 0
    items_to_bd = list()
    for item in items:
        name, quantity, sum = item['name'], item['quantity'], item['sum']
        txt = str(num) + f'. \'{name}\' place {quantity} == {sum / 100.0}\n'
        items_to_bd.append(txt)
        num = num + 1

    data_from_db = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data_from_db['order'])
    order.data = items_to_bd
    order.price = data['document']['receipt']['totalSum']
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})
    await storage.set_state(user=message.from_user.id, state=UserState.checking_bill)

    names = []
    for item in items:
        quant = item['quantity']
        while quant > 0:
            names.append(item['name'])
            quant = quant - 1

    message_text = ''
    print(items)
    data_from_db = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data_from_db['order'])
    for user in order.participants:
        sum = 0
        user_chat = await bot.get_chat(chat_id=user)
        user_data = await storage.get_data(user=user)
        message_text += f'Пользователь \'{user_chat.full_name}\' заказал:\n'
        i = 1
        for dish in user_data['dishes']:
            output = get_close_matches(dish, names, n=1, cutoff=0.60)
            if output:
                names.remove(output[0])
                for item in items:
                    if item['name'] == output[0]:
                        name = item['name']
                        price = item['price']
                        message_text += f'{i}. {name} = {price/100.0}\n'
                        i += 1
                        item['quantity'] -= 1
                        item['sum'] -= item['price']
                        sum += item['price']
                        break
        message_text += f'Итого {sum / 100.0}\n\n'
    message_text += 'Не удалось распознать:\n'
    i = 1
    for item in items:
        if item['quantity'] > 0:
            name, quantity, sum = item['name'], item['quantity'], item['sum']
            message_text += str(i) + f'. \'{name}\' place {quantity} == {sum / 100.0}\n'
            i += 1
    await bot.send_message(message.chat.id, message_text)


@dp.message_handler(commands=['addbill'], chat_type='group', state='*',
                  #  chat_state=ChatState.checking_bill
)
async def add_bill_item(message: Message):
    data_from_db = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data_from_db['order'])
    items = order.data
    positions = message.get_args().split(' ')

    for p in positions:
        del items[int(p)]
    await bot.send_message(message.chat.id, items)



