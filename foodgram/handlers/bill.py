from io import BytesIO

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

    message_text = ''
    num = 0
    items_to_bd = list()
    for item in items:
        name, quantity, sum = item['name'], item['quantity'], item['sum']
        txt = str(num) + f'. \'{name}\' place {quantity} == {sum / 100.0}\n'
        message_text += txt
        items_to_bd.append(txt)
        num = num + 1

    await bot.send_message(message.chat.id, message_text)

    data_from_db = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data_from_db['order'])
    order.data = items_to_bd
    order.price = data['document']['receipt']['totalSum']
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})
    await storage.set_state(user=message.from_user.id, state=UserState.checking_bill)



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





