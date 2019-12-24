import io
import logging
import hashlib
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

logging.basicConfig(level=logging.DEBUG)

# токен  бота
API_TOKEN = '1056772125:AAFQrxSVgSzMO3Ihc9Rb3n4Uqm9pYZAa5NQ'
# создание бота и диспетчера
bot = Bot(token=API_TOKEN)
bot.parse_mode = 'HTML'

db_storage = FirebaseStorage('./credentials.json')
storage = MemoryStorage()
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
    finish_order = "finish_order"


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
    await storage.set_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order_info)})
    await storage.set_state(chat=message.chat.id, state=ChatState.gather_places)

    message_text = "Привет, будем заказывать\n" \
                   "<b>%s</b> - инициатор заказа, будет иметь основные права и обязанности. " \
                   "Пишите места командой" % message.from_user.first_name
    
    inline_button_text = "Предложить место из списка"
    keyboard_markup = types.InlineKeyboardMarkup()
    keyboard_markup.add(
        types.InlineKeyboardButton(inline_button_text, switch_inline_query_current_chat= '/addPlace ')
    )
    
    await bot.send_message(message.chat.id, message_text, reply_markup=keyboard_markup)

    # информируем главного что он главный
    # message_text = "Привет, %s! Ты решил сделать заказ в чате %s \n 😎 " \
    #                % (message.from_user.first_name, message.chat.title)
    # await bot.send_message(message.from_user.id, message_text)


@dp.message_handler(commands=['addPlace'], chat_type='group', chat_state=ChatState.gather_places)
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


@dp.message_handler(commands=['startPoll'], chat_type='group', is_order_owner=True, chat_state=ChatState.gather_places)
async def if_start_poll(message: types.Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])

    if len(data['order']['places']) < 1:
        return

    if len(data['order']['places']) == 1:
        winner_option = data['order']['places']
        inline_button_text = "Принять участие в формировании заказа"
        inline_button_data = str(message.chat.id)
        keyboard_markup = types.InlineKeyboardMarkup()
        keyboard_markup.add(
            types.InlineKeyboardButton(inline_button_text, callback_data=inline_button_data)
        )
        message_text = f"Вариант " + str(winner_option[0]) + " набрал наибольшее количество голосов."
        await bot.send_message(message.chat.id, message_text, reply_markup=keyboard_markup)
        data = await storage.get_data(chat=message.chat.id)
        order = OrderInfo(**data['order'])
        order.chosen_place = winner_option
        await storage.update_data(chat=message.chat.id, data=data)
        await storage.set_state(chat=message.chat.id, state=ChatState.making_order)
        return

    await storage.set_state(chat=message.chat.id, state=ChatState.poll)

    question = "Из какого места заказать еду?"
    sent_message = await bot.send_poll(message.chat.id, question, order.places, None, None)

    await storage.update_data(chat=message.chat.id, data={'poll_message_id': sent_message.message_id})


@dp.message_handler(commands=['showPlace'], chat_type='group', is_order_owner=True, chat_state=ChatState.poll)
async def if_show_place(message: types.Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    order.chosen_place = winer_option

    poll_message_id = data['poll_message_id']
    poll = await bot.stop_poll(message.chat.id, poll_message_id)

    # [print(opt)]
    poll.options.sort(key=lambda o: o.voter_count, reverse=True)
    winner_option = poll.options[0]

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
    if 'poll_message_id' in data:
        data.pop('poll_message_id')
        await storage.set_data(chat=message.chat.id, data=data)


@dp.message_handler(commands='finishOrder', chat_type='group', is_order_owner=True, chat_state=[ChatState.making_order])
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


@dp.message_handler(commands='closeOrder', chat_type='group', is_order_owner=True, chat_state=ChatState.waiting_order)
async def if_close_order(message: types.Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    order.date_delivered = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})
    # todo notify all

    stats = await collect_data(bot, storage, message.chat.id)
    await storage.add_stats(stats)

    for user in order.participants:
        await storage.reset_state(user=user, with_data=True)
    await storage.reset_state(chat=message.chat.id, with_data=True)

    message_text = "Текущий заказ завершен."
    await bot.send_message(message.chat.id, message_text)


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

    message_text = f"Вы приняли участие в формирование заказа, созданного в \"{chat.title}\""
    
    inline_button_text = "Добавить блюдо из списка"
    keyboard_markup = types.InlineKeyboardMarkup()
    keyboard_markup.add(
        types.InlineKeyboardButton(inline_button_text, switch_inline_query_current_chat= '/add ')
    )
    
    await bot.send_message(query.from_user.id, message_text, reply_markup=keyboard_markup)


@dp.message_handler(commands=['add'], chat_type='private', state='*', user_state=UserState.making_order)
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
    state='*', user_state=UserState.making_order
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


@dp.message_handler(commands=['list'], chat_type='private', state='*', user_state=UserState.making_order)
async def if_add_in_private(message: types.Message):
    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    dishes = [str(i + 1) + '. ' + dishes[i] for i in range(len(dishes))]
    message_text = 'Блюда в заказе:\n' + '\n'.join(dishes) if (len(dishes) > 0) else 'Ваш заказ пуст'
    await bot.send_message(message.from_user.id, message_text)


@dp.message_handler(commands=['finish'], chat_type='private', state='*', user_state=UserState.making_order)
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


@dp.message_handler(content_types=['photo'])
async def handle_docs_photo(message: types.Message):

    photos = message.photo
    if len(photos) < 1:
        return

    image_bytes = io.BytesIO()
    await photos[0].download(image_bytes)

    bills = await decode_qr_bill(image_bytes)
    if len(bills) < 1:
        await bot.send_message(message.from_user.id, 'Невозможно декодировать QR код.')
        return

    await bot.send_message(message.from_user.id, 'Выполняется поиск чека...')
    data = await get_bill_data(bills[0])
    if data is None:
        await bot.send_message(message.from_user.id, 'Не удалось найти чек.')
        return

    items = data['document']['receipt']['items']
    message_text = ''
    for item in items:
        name, quantity, sum = item['name'], item['quantity'], item['sum']
        message_text += f'\'{name}\' x {quantity} == {sum / 100.0}\n'
    await bot.send_message(message.from_user.id, message_text)


@dp.message_handler(commands=['help'], state='*')
async def help_command(message):
    help_message = "Добавь меня в беседу. Потом:\n" \
                   "/start - запуск заказа. Нажавший - ответственный\n" \
                   "/addPlace - добавление места заказа\n" \
                   "/startPoll - выбор места заказа (после добавления всех мест)\n" \
                   "/showPlace - победившее место + принять участие в заказе\n" \
                   "/cancel - отмена заказа\n" \
                   "После выбора места можно делать заказ в личном диалоге с ботом:\n" \
                   "/add - добавить пункт заказа\n" \
                   "/change - изменить пункт заказа\n" \
                   "/delete - убрать пункт заказа\n" \
                   "/list - вывод пунктов заказа\n" \
                   "/finish - закончить формирование заказа\n" \
                   "/status - ответственному - проверить состояние заказа\n" \
                   "/finishOrder - ответственному - закончить формирование заказа\n" \
                   "/endOrder - ответственному - заказ выполнен\n"
    await bot.send_message(message.chat.id, help_message)


@dp.message_handler(commands=['change'], regexp='/change \\d+ \\w+', chat_type='private', state='*', user_state=UserState.making_order)
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

		
# inline mode
# DON'T FORGET to write "/setinline" to BotFather to change inline queries status.
@dp.inline_handler(lambda query: query.query.startswith('/add'), state=UserState.making_order)
async def inline_dishes(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    lst = db_storage.get_dishes(inline_query.from_user.username)
    inpLst = []
    if len(parts) < 2:
        inpLst = list(map(lambda x: InlineQueryResultArticle(
            id=hashlib.md5(x.encode()).hexdigest(),
            title = x,
            input_message_content=InputTextMessageContent('/add ' + x)
            ), lst))
    else:
        inpLst = list(map(lambda x: InlineQueryResultArticle(
            id=hashlib.md5(x.encode()).hexdigest(),
            title = x,
            input_message_content=InputTextMessageContent('/add ' + x)
            ), list(filter(lambda x: x.lower().startswith(parts[1].lower()), lst))))
    await bot.answer_inline_query(inline_query.id, results=inpLst, cache_time=1)
    
@dp.inline_handler(lambda query: query.query.startswith('/addPlace'))
async def inline_cafe(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    lst = db_storage.get_places(inline_query.from_user.username)
    if len(parts) < 2:
        inpLst = list(map(lambda x: InlineQueryResultArticle(
            id=hashlib.md5(x.encode()).hexdigest(),
            title = x,
            input_message_content=InputTextMessageContent('/addPlace ' + x)
            ), lst))
    else:
        inpLst = list(map(lambda x: InlineQueryResultArticle(
            id=hashlib.md5(x.encode()).hexdigest(),
            title = x,
            input_message_content=InputTextMessageContent('/addPlace ' + x)
            ), list(filter(lambda x: x.lower().startswith(parts[1].lower()), lst))))
    await bot.answer_inline_query(inline_query.id, results=inpLst, cache_time=1)


@dp.message_handler(commands='endOrder', chat_type='group', is_order_owner=True, chat_state=[ChatState.making_order])
async def if_finish_order(message: types.Message):
    message_text = 'Заказ беседы ' + message.chat.first_name +' выполнен.'
    data = await storage.get_data(chat=message.chat.id)
    participants = data['order']['participants']
    for user in participants:
        print(user)
        user_chat = await bot.get_chat(chat_id=user)
        await bot.send_message(user_chat, message_text)
    await storage.set_state(chat=message.chat.id, state=ChatState.finish_order)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
