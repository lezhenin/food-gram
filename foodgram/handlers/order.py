from datetime import datetime

from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from .. import bot, dp, storage, db_storage
from ..model.state import ChatState, UserState
from ..model.orderinfo import OrderInfo
from ..utils import stats


# None is default value of chat_state, todo initialize with idle
@dp.message_handler(commands=['start'], chat_type='group', chat_state=[ChatState.idle, None])
async def if_start(message: Message):
    order_info = OrderInfo.from_message(message)
    order_info.date_started = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await storage.set_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order_info)})
    await storage.set_state(chat=message.chat.id, state=ChatState.gather_places)

    message_text = "Привет, будем заказывать\n" \
                   "<b>%s</b> - инициатор заказа, будет иметь основные права и обязанности. " \
                   "Пишите места командой" % message.from_user.first_name

    inline_button_text = "Предложить место из списка"
    keyboard_markup = InlineKeyboardMarkup()
    keyboard_markup.add(
        InlineKeyboardButton(inline_button_text, switch_inline_query_current_chat='/addplace ')
    )

    await bot.send_message(message.chat.id, message_text, reply_markup=keyboard_markup)


@dp.message_handler(commands='finishorder', chat_type='group', is_order_owner=True, chat_state=[ChatState.making_order])
async def if_finish_order(message: Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    order.date_finished = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})

    message_text = ''
    for user in order.participants:
        user_chat = await bot.get_chat(chat_id=user)
        user_data = await storage.get_data(user=user)
        message_text += f'Пользователь \'{user_chat.full_name}\' заказал:\n'
        for i, dish in enumerate(user_data['dishes']):
            message_text += f'{i + 1}. {dish}\n'
        message_text += '\n'
    await bot.send_message(message.from_user.id, message_text)

    await storage.set_state(chat=message.chat.id, state=ChatState.waiting_order)


@dp.message_handler(commands='closeorder', chat_type='group', is_order_owner=True, chat_state=ChatState.waiting_order)
async def if_close_order(message: Message):
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
async def if_cancel(message: Message):
    data = await storage.get_data(chat=message.chat.id)
    if 'order' in data:
        participants = data['order']['participants']
        for user in participants:
            await storage.reset_state(user=user, with_data=True)

    await storage.reset_state(chat=message.chat.id, with_data=True)

    message_text = "Текущий заказ отменен."
    await bot.send_message(message.chat.id, message_text)


@dp.callback_query_handler(user_state=[UserState.idle, None])
async def inline_kb_answer_callback_handler(query: CallbackQuery):
    chat = await bot.get_chat(chat_id=query.data)
    data = await storage.get_data(chat=chat.id)
    order = OrderInfo(**data['order'])
    order.add_participant(query.from_user.id)

    await storage.update_data(chat=chat.id, data={'order': OrderInfo.as_dict(order)})

    await storage.set_state(user=query.from_user.id, state=UserState.making_order)
    await storage.update_data(user=query.from_user.id, data={'order_chat_id': chat.id})

    message_text = f"Вы приняли участие в формировании заказа, созданного в \"{chat.title}\""

    if not db_storage.get_dishes(query.from_user.id):
        await bot.send_message(query.from_user.id, message_text)
    else:
        inline_button_text = "Добавить блюдо из списка"
        keyboard_markup = InlineKeyboardMarkup()
        keyboard_markup.add(
            InlineKeyboardButton(inline_button_text, switch_inline_query_current_chat='/add ')
        )

        await bot.send_message(query.from_user.id, message_text, reply_markup=keyboard_markup)
