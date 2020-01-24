from io import BytesIO

from aiogram.types import Message

from .. import bot, dp, storage
from ..model.state import ChatState
from ..model.orderinfo import OrderInfo
from ..utils import bill


@dp.message_handler(content_types=['photo'], state='*', chat_state=[ChatState.waiting_order])
async def handle_docs_photo(message: Message):
    photos = message.photo
    if len(photos) < 1:
        return

    image_bytes = BytesIO()
    await photos[2].download(image_bytes)

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
    for item in items:
        name, quantity, sum = item['name'], item['quantity'], item['sum']
        message_text += f'\'{name}\' place {quantity} == {sum / 100.0}\n'
    await bot.send_message(message.chat.id, message_text)

    data_from_db = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data_from_db['order'])
    order.price = data['document']['receipt']['totalSum']
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})
