import io
import logging
import hashlib

from datetime import datetime, timedelta

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import InlineQuery, InputTextMessageContent, InlineQueryResultArticle
from aiogram.utils import executor

from orderinfo import OrderInfo
from extensions.filters import OrderOwnerFilter, UserStateFilter, ChatStateFilter, ChatTypeFilter
from extensions.firebase import FirebaseStorage

from utils.bill import decode_qr_bill, get_bill_data
from utils import stats

logging.basicConfig(level=logging.DEBUG)

# токен  бота
API_TOKEN = '1056772125:AAFQrxSVgSzMO3Ihc9Rb3n4Uqm9pYZAa5NQ'
# создание бота и диспетчера
bot = Bot(token=API_TOKEN)
bot.parse_mode = 'HTML'

db_storage = FirebaseStorage('./testcred.json')
storage = db_storage
# storage = FirebaseStorage('./testcred.json')
# storage = MemoryStorage()

dp = Dispatcher(bot, storage=storage)

dp.filters_factory.bind(OrderOwnerFilter)
dp.filters_factory.bind(UserStateFilter)
dp.filters_factory.bind(ChatStateFilter)
dp.filters_factory.bind(ChatTypeFilter)


class ChatState:
    idle = "idle"
    gather_places = "gather_places"
    poll = "poll"
    making_order = "making_order"
    waiting_order = "waiting_order"


class UserState:
    idle = "idle"
    making_order = "making_order"
    finish_order = "finish_order"


@dp.message_handler(commands=['start'], chat_type='private')
async def if_start_in_private(message: types.Message):
    if message.chat.type == 'private':
        message_text = "%s, привет. " \
                       "Команда /help поможет разобраться как что работает" % message.from_user.first_name
        await bot.send_message(message.chat.id, message_text)
        return


# None is default value of chat_state, todo initialize with idle
@dp.message_handler(commands=['start'], chat_type='group', chat_state=[ChatState.idle, None])
async def if_start(message: types.Message):
    order_info = OrderInfo.from_message(message)
    order_info.date_started = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await storage.set_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order_info)})
    await storage.set_state(chat=message.chat.id, state=ChatState.gather_places)

    message_text = "Привет, будем заказывать\n" \
                   "<b>%s</b> - инициатор заказа, будет иметь основные права и обязанности. " \
                   "Пишите места командой" % message.from_user.first_name
    
    inline_button_text = "Предложить место из списка"
    keyboard_markup = types.InlineKeyboardMarkup()
    keyboard_markup.add(
        types.InlineKeyboardButton(inline_button_text, switch_inline_query_current_chat='/addplace ')
    )
    
    await bot.send_message(message.chat.id, message_text, reply_markup=keyboard_markup)


@dp.message_handler(commands=['addplace'], chat_type='group', chat_state=ChatState.gather_places)
async def if_add_place(message: types.Message):
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


@dp.message_handler(commands=['startpoll'], chat_type='group', is_order_owner=True, chat_state=ChatState.gather_places)
async def if_start_poll(message: types.Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])

    if len(order.places) < 1:
        return

    if len(order.places) == 1:
        winner_option = order.places[0]
        inline_button_text = "Принять участие в формировании заказа"
        inline_button_data = str(message.chat.id)
        keyboard_markup = types.InlineKeyboardMarkup()
        keyboard_markup.add(
            types.InlineKeyboardButton(inline_button_text, callback_data=inline_button_data)
        )
        message_text = f"Только один вариант \"" + str(winner_option) + "\" был предложен."
        await bot.send_message(message.chat.id, message_text, reply_markup=keyboard_markup)
        order.chosen_place = winner_option
        data['order'] = OrderInfo.as_dict(order)
        await storage.set_data(chat=message.chat.id, data=data)
        await storage.set_state(chat=message.chat.id, state=ChatState.making_order)
        return

    await storage.set_state(chat=message.chat.id, state=ChatState.poll)

    question = "Из какого места заказать еду?"
    sent_message = await bot.send_poll(message.chat.id, question, order.places, None, None)

    await storage.update_data(chat=message.chat.id, data={'poll_message_id': sent_message.message_id})


@dp.message_handler(commands=['finishpoll'], chat_type='group', is_order_owner=True, chat_state=ChatState.poll)
async def if_show_place(message: types.Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])

    poll_message_id = data['poll_message_id']
    poll = await bot.stop_poll(message.chat.id, poll_message_id)

    poll.options.sort(key=lambda o: o.voter_count, reverse=True)
    winner_option = poll.options[0]
    order.chosen_place = winner_option.text

    inline_button_text = "Принять участие в формировании заказа"
    inline_button_data = str(message.chat.id)

    keyboard_markup = types.InlineKeyboardMarkup()
    keyboard_markup.add(
        types.InlineKeyboardButton(inline_button_text, callback_data=inline_button_data)
    )

    message_text = f"Вариант \"{winner_option.text}\" набрал наибольшее количество голосов."
    await bot.send_message(message.chat.id, message_text, reply_markup=keyboard_markup)

    await storage.set_state(chat=message.chat.id, state=ChatState.making_order)

    data = await storage.get_data(chat=message.chat.id)
    data['order'] = OrderInfo.as_dict(order)
    if 'poll_message_id' in data:
        data.pop('poll_message_id')
    await storage.set_data(chat=message.chat.id, data=data)


@dp.message_handler(commands='finishorder', chat_type='group', is_order_owner=True, chat_state=[ChatState.making_order])
async def if_finish_order(message: types.Message):

    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    order.date_finished = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})

    message_text = ''
    for user in order.participants:
        user_chat = await bot.get_chat(chat_id=user)
        # todo check state
        user_data = await storage.get_data(user=user)
        message_text += f'Пользователь \'{user_chat.full_name}\' заказал:\n'
        for i, dish in enumerate(user_data['dishes']):
            message_text += f'{i+1}. {dish}\n'
        message_text += '\n'
    await bot.send_message(message.from_user.id, message_text)

    await storage.set_state(chat=message.chat.id, state=ChatState.waiting_order)


@dp.message_handler(commands='closeorder', chat_type='group', is_order_owner=True, chat_state=ChatState.waiting_order)
async def if_close_order(message: types.Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    order.date_delivered = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})

    stats_data = await stats.collect_data(bot, storage, message.chat.id)
    await storage.add_stats(stats_data)

    message_text = ""
    for user in stats_data['participants']:
        username = user['username']
        if username is not None:
            message_text += f"@{username}, "
        else:
            await bot.send_message(user['user_id'], "Заказ доставлен.")
    if len(message_text) > 0:
        message_text += "заказ доставлен."
    else:
        message_text += "Заказ доставлен. "
    message_text += "Текущий заказ завершен."
    await bot.send_message(message.chat.id, message_text)

    for user in order.participants:
        await storage.reset_state(user=user, with_data=True)
    await storage.reset_state(chat=message.chat.id, with_data=True)


@dp.message_handler(commands='cancel', chat_type='group', is_order_owner=True, chat_state_not=[ChatState.idle, None])
async def if_cancel(message: types.Message):
    data = await storage.get_data(chat=message.chat.id)
    if 'order' in data:
        participants = data['order']['participants']
        for user in participants:
            await storage.reset_state(user=user, with_data=True)

    await storage.reset_state(chat=message.chat.id, with_data=True)

    message_text = "Текущий заказ отменен."
    await bot.send_message(message.chat.id, message_text)


@dp.callback_query_handler(user_state=[UserState.idle, None])
async def inline_kb_answer_callback_handler(query: types.CallbackQuery):
    chat = await bot.get_chat(chat_id=query.data)
    data = await storage.get_data(chat=chat.id)
    order = OrderInfo(**data['order'])
    order.add_participant(query.from_user.id)

    await storage.update_data(chat=chat.id, data={'order': OrderInfo.as_dict(order)})

    await storage.set_state(user=query.from_user.id, state=UserState.making_order)
    await storage.update_data(user=query.from_user.id, data={'order_chat_id': chat.id})

    message_text = f"Вы приняли участие в формировании заказа, созданного в \"{chat.title}\""
    
    if db_storage.get_dishes(query.from_user.id) == []:
        await bot.send_message(query.from_user.id, message_text)
    else:
        inline_button_text = "Добавить блюдо из списка"
        keyboard_markup = types.InlineKeyboardMarkup()
        keyboard_markup.add(
            types.InlineKeyboardButton(inline_button_text, switch_inline_query_current_chat= '/add ')
        )
    
        await bot.send_message(query.from_user.id, message_text, reply_markup=keyboard_markup)


@dp.message_handler(commands=['add'], chat_type='private', state='*', user_state=[UserState.making_order, UserState.finish_order])
async def if_add_in_private(message: types.Message):
    parts = message.text.split(' ', maxsplit=1)
    if len(parts) < 2:
        return

    data = await storage.get_data(user=message.from_user.id)
    dish = parts[1]
    dishes = data.get('dishes', [])
    dishes.append(dish)

    await storage.update_data(user=message.from_user.id, data={'dishes': dishes})


@dp.message_handler(
    commands=['delete'], regexp='/delete \\d+\\s*', chat_type='private',
    state='*', user_state=[UserState.making_order, UserState.finish_order]
)
async def if_add_in_private(message: types.Message):
    parts = message.text.split(' ', maxsplit=1)
    if len(parts) < 2:
        return

    index = int(parts[1])
    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    if index - 1 < len(dishes):
        del dishes[index-1]
        await storage.update_data(user=message.from_user.id, data={'dishes': dishes})


@dp.message_handler(commands=['change'], regexp='/change \\d+ \\w+', chat_type='private', state='*', user_state=[UserState.making_order, UserState.finish_order])
async def if_add_in_private(message: types.Message):
    parts = message.text.split(' ', maxsplit=2)
    if len(parts) < 3:
        return
    index = int(parts[1])
    data = await storage.get_data(user=message.from_user.id)

    dishes = data.get('dishes', [])
    if index - 1 < len(dishes):
        dishes[index-1] = parts[2]
        await storage.update_data(user=message.from_user.id, data={'dishes': dishes})


@dp.message_handler(commands=['list'], chat_type='private', state='*', user_state=[UserState.making_order, UserState.finish_order])
async def if_add_in_private(message: types.Message):
    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    dishes = [str(i + 1) + '. ' + dishes[i] for i in range(len(dishes))]
    message_text = 'Блюда в заказе:\n' + '\n'.join(dishes) if (len(dishes) > 0) else 'Ваш заказ пуст'
    await bot.send_message(message.from_user.id, message_text)


@dp.message_handler(commands=['finish'], chat_type='private', state='*', user_state=[UserState.making_order, UserState.finish_order])
async def if_add_in_private(message: types.Message):
    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    dishes = [str(i + 1) + '. ' + dishes[i] for i in range(len(dishes))]
    if len(dishes) > 0:
        message_text = 'Заказ завершен. Блюда в заказе:\n' + '\n'.join(dishes)
        await storage.set_state(user=message.from_user.id, state=UserState.finish_order)
    else:
        message_text = 'Вы ничего не добавили в заказ.'

    await bot.send_message(message.from_user.id, message_text)


@dp.message_handler(commands=['status'], chat_type='private', is_order_owner=True,  state='*', user_state=[UserState.making_order, UserState.finish_order])
async def if_status_in_private(message: types.Message):
    data = await storage.get_data(user=message.from_user.id)
    chat_id = data['order_chat_id']
    data = await storage.get_data(chat=chat_id)
    message_text = ''
    participants = data['order']['participants']
    for user in participants:
        user_chat = await bot.get_chat(chat_id=user)
        state = await storage.get_state(user=user)
        if state == UserState.making_order:
            message_text += f'Пользователь \'{user_chat.full_name}\' формирует заказ\n'
        elif state == UserState.finish_order:
            message_text += f'Пользователь \'{user_chat.full_name}\' завершил формирование заказа\n'

    await bot.send_message(message.from_user.id, message_text)


@dp.message_handler(content_types=['photo'], state='*', chat_state=[ChatState.waiting_order])
async def handle_docs_photo(message: types.Message):

    photos = message.photo
    if len(photos) < 1:
        return

    image_bytes = io.BytesIO()
    await photos[2].download(image_bytes)

    bills = await decode_qr_bill(image_bytes)
    if len(bills) < 1:
        await bot.send_message(message.chat.id, 'Невозможно декодировать QR код.')
        return

    await bot.send_message(message.chat.id, 'Выполняется поиск чека...')
    data = await get_bill_data(bills[0])
    if data is None:
        await bot.send_message(message.chat.id, 'Не удалось найти чек.')
        return

    items = data['document']['receipt']['items']
    message_text = ''
    for item in items:
        name, quantity, sum = item['name'], item['quantity'], item['sum']
        message_text += f'\'{name}\' x {quantity} == {sum / 100.0}\n'
    await bot.send_message(message.chat.id, message_text)

    data_from_db = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data_from_db['order'])
    order.price = data['document']['receipt']['totalSum']
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})


@dp.message_handler(commands=['stats'], state='*')
async def if_stats(message: types.Message):
    if message.chat.type == 'private':
        stats_url = stats.get_user_url(message.chat.id)
    elif message.chat.type == 'group':
        stats_url = stats.get_chat_url(message.chat.id)
    else:
        return

    message_text = f'Ваша статистика доступна по ссылке {message.link(stats_url)}'
    await bot.send_message(message.chat.id, message_text)


@dp.message_handler(commands=['help'], state='*')
async def help_command(message):
    help_message = "Добавь меня в беседу. Потом:\n" \
                   "/start - начать заказ. Нажавший - ответственный\n" \
                   "/addplace - предложить место заказа для голосования\n" \
                   "/startpoll - начать голосование для выбора места заказа\n" \
                   "/finishpoll - завершить голосование\n" \
                   "/cancel - отмена заказа\n" \
                   "\nПосле выбора места можно делать заказ в личном диалоге с ботом:\n" \
                   "/add - добавить пункт заказа\n" \
                   "/change - изменить пункт заказа\n" \
                   "/delete - убрать пункт заказа\n" \
                   "/list - вывод пунктов заказа\n" \
                   "/finish - закончить формирование заказа\n" \
                   "/status - ответственному - проверить состояние заказа\n" \
                   "\nПосле выбора блюд ответственный завершает заказ в общем чате:\n" \
                   "/finishorder - закончить формирование заказа\n" \
                   "/closeorder - заказ выполнен\n" \
                   "\n/stats - получить ссылку для просмотра статистики\n"
    await bot.send_message(message.chat.id, help_message)


@dp.inline_handler(lambda query: query.query.startswith('/add'), state=UserState.making_order)
async def inline_dishes(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    lst = db_storage.get_dishes(inline_query.from_user.id, date_from)
    inpLst = []
    if len(parts) < 2:
        inpLst = list(map(lambda x: InlineQueryResultArticle(
            id=hashlib.md5(x.encode()).hexdigest(),
            title=x,
            input_message_content=InputTextMessageContent('/add ' + x)
            ), lst))
    else:
        inpLst = list(map(lambda x: InlineQueryResultArticle(
            id=hashlib.md5(x.encode()).hexdigest(),
            title=x,
            input_message_content=InputTextMessageContent('/add ' + x)
            ), list(filter(lambda x: x.lower().startswith(parts[1].lower()), lst))))
    await bot.answer_inline_query(inline_query.id, results=inpLst, cache_time=1)


@dp.inline_handler(lambda query: query.query.startswith('/addplace'))
async def inline_cafe(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    lst = db_storage.get_places(inline_query.from_user.id, date_from)
    if lst == []:
        lst = ["Теремок. Блины", "Макдоналдс", "Бургер Кинг", "Баскин Роббинс", "Буше торты", "Bekitzer Бекицер", "Crispy Pizza", "Чебуречная Брынза", "Таверна Сиртаки", "Суши-бар Кидо"]
    if len(parts) < 2:
        inpLst = list(map(lambda x: InlineQueryResultArticle(
            id=hashlib.md5(x.encode()).hexdigest(),
            title=x,
            input_message_content=InputTextMessageContent('/addplace ' + x)
            ), lst))
    else:
        inpLst = list(map(lambda x: InlineQueryResultArticle(
            id=hashlib.md5(x.encode()).hexdigest(),
            title=x,
            input_message_content=InputTextMessageContent('/addplace ' + x)
            ), list(filter(lambda x: x.lower().startswith(parts[1].lower()), lst))))
    await bot.answer_inline_query(inline_query.id, results=inpLst, cache_time=1)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
