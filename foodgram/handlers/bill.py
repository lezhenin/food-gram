from io import BytesIO
from difflib import get_close_matches

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from .. import bot, dp, storage
from ..model.state import ChatState, UserState
from ..utils import bill


@dp.message_handler(content_types=['photo'], state='*', chat_state=[ChatState.waiting_order])
async def handle_docs_photo(message: Message):

    if not message.caption.startswith('/bill'):
        return

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

    await storage.set_state(chat=message.chat.id, state=UserState.checking_bill)
    data_from_db = await storage.get_data(chat=message.chat.id)
    matched_bill = await match_bill_items(data_from_db['order']['participants'], items)
    await storage.update_data(chat=message.chat.id, data={'matched_bill': matched_bill})

    message_text = bill_to_str(matched_bill)
    await bot.send_message(message.chat.id, message_text, reply_markup=make_keyboard())


@dp.message_handler(commands='take', chat_type='group', is_order_participant=True, chat_state=ChatState.checking_bill)
async def if_add_to_bill(message: Message):
    arg = message.get_args()
    data_from_db = await storage.get_data(chat=message.chat.id)
    matched_bill = data_from_db['matched_bill']
    for item in matched_bill['other']:
        if item['name'].strip() == arg.strip():
            position = item
            for person in matched_bill['matched']:
                if person['user_id'] == message.from_user.id:
                    person['items'].append({'name': position['name'], 'price': position['price']})
                    if position['quantity'] == 1:
                        matched_bill['other'].remove(item)
                    else:
                        item['quantity'] -= 1
                        item['sum'] -= item['price']
                    break
    await storage.update_data(chat=message.chat.id, data={'matched_bill': matched_bill})
    message_text = bill_to_str(matched_bill)
    await bot.send_message(message.chat.id, message_text, reply_markup=make_keyboard())


@dp.message_handler(commands='drop', chat_type='group', is_order_participant=True, chat_state=ChatState.checking_bill)
async def if_add_to_bill(message: Message):
    arg = message.get_args()
    data_from_db = await storage.get_data(chat=message.chat.id)
    matched_bill = data_from_db['matched_bill']
    for person in matched_bill['matched']:
        if person['user_id'] == message.from_user.id:
            for item in person['items']:
                if item['name'].strip() == arg.strip():
                    matched_bill['other'].append({
                        'name': item['name'],
                        'quantity': 1,
                        'sum': item['price'],
                        'price': item['price']
                    })
                    person['items'].remove(item)
                    break
    await storage.update_data(chat=message.chat.id, data={'matched_bill': matched_bill})
    message_text = bill_to_str(matched_bill)
    await bot.send_message(message.chat.id, message_text, reply_markup=make_keyboard())


async def match_bill_items(participants, items):
    names = make_positions_list(items)
    matched_bill = {'matched': [], 'other': []}
    for user in participants:
        matched_dish = []
        user_chat = await bot.get_chat(chat_id=user)
        user_data = await storage.get_data(user=user)
        for dish in user_data['dishes']:
            # get_close_matches(word, posibilities, n, cutoff)
            # 'word' is the word for which you want to find close matches
            # 'posibilities' is a list of sequences against which to match the word
            # [optional] 'n' is maximum number of close matches
            # [optional] 'cutoff' - where to stop considering a word as a match
            # (0.99 being the closest to word while 0.0 being otherwise)
            output = get_close_matches(dish, names, n=1, cutoff=0.60)
            if output:
                names.remove(output[0])
                for item in items:
                    if item['name'] == output[0]:
                        name, price = item['name'], item['price']
                        matched_dish.append({'name': name, 'price': price})
                        item['quantity'] -= 1
                        item['sum'] -= item['price']
                        break
        matched_bill['matched'].append({'user_id': user, 'username': user_chat.full_name, 'items': matched_dish})
    for item in items:
        if item['quantity'] > 0:
            name, quantity, sum, price = item['name'], item['quantity'], item['sum'], item['price']
            matched_bill['other'].append({'name': name, 'quantity': quantity, 'sum': sum, 'price': price})

    return matched_bill


def bill_to_str(matched_bill):
    message_text = ''
    for user in matched_bill['matched']:
        sum = 0
        username = user['username']
        if len(user['items']) == 0:
            continue
        message_text += f'Пользователь \'{username}\' заказал:\n'
        i = 1
        for item in user['items']:
            name, price = item['name'], item['price']
            message_text += f'{i}. {name} = {price / 100.0}\n'
            i += 1
            sum += price
        message_text += f'Итого {sum / 100.0}\n\n'
    if len(matched_bill['other']) == 0:
        return message_text
    message_text += 'Не удалось распознать:\n'
    i = 1
    for item in matched_bill['other']:
        name, quantity, sum = item['name'], item['quantity'], item['sum']
        message_text += f'{i}. {name} x {quantity} = {sum / 100.0}\n'
        i += 1
    return message_text


def make_positions_list(items):
    names = []
    for item in items:
        quant = item['quantity']
        while quant > 0:
            names.append(item['name'])
            quant = quant - 1
    return names


def make_keyboard():
    add_button = InlineKeyboardButton("Опознать блюдо", switch_inline_query_current_chat='/take ')
    delete_button = InlineKeyboardButton("Неверное распознавание", switch_inline_query_current_chat='/drop ')
    keyboard_markup = InlineKeyboardMarkup()
    keyboard_markup.row(add_button)
    keyboard_markup.row(delete_button)
    return keyboard_markup
