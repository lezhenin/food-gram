from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from .. import bot, dp, storage
from ..model.state import ChatState
from ..model.orderinfo import OrderInfo


@dp.message_handler(commands=['addplace'], chat_type='group', chat_state=ChatState.gather_places)
async def if_add_place(message: Message):
    new_place = message.get_args()
    if not new_place:
        return

    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])
    order.add_place(new_place)
    await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})

    message_text = f"Место \"{new_place}\" было добавлено. Места участвующие в голосовании: {', '.join(order.places)}."
    await bot.send_message(message.chat.id, message_text)


@dp.message_handler(commands=['startpoll'], chat_type='group', is_order_owner=True, chat_state=ChatState.gather_places)
async def if_start_poll(message: Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])

    if len(order.places) < 1:
        return

    if len(order.places) == 1:
        winner_option = order.places[0]
        inline_button_text = "Принять участие в формировании заказа"
        inline_button_data = str(message.chat.id)
        keyboard_markup = InlineKeyboardMarkup()
        keyboard_markup.add(
            InlineKeyboardButton(inline_button_text, callback_data=inline_button_data)
        )
        message_text = f"Только один вариант \"" + str(winner_option) + "\" был предложен."
        await bot.send_message(message.chat.id, message_text, reply_markup=keyboard_markup)
        order.chosen_place = winner_option
        await storage.update_data(chat=message.chat.id, data={'order': OrderInfo.as_dict(order)})
        await storage.set_state(chat=message.chat.id, state=ChatState.making_order)
        return

    await storage.set_state(chat=message.chat.id, state=ChatState.poll)

    question = "Из какого места заказать еду?"
    sent_message = await bot.send_poll(message.chat.id, question, order.places, None, None)

    await storage.update_data(chat=message.chat.id, data={'poll_message_id': sent_message.message_id})


@dp.message_handler(commands=['finishpoll'], chat_type='group', is_order_owner=True, chat_state=ChatState.poll)
async def if_show_place(message: Message):
    data = await storage.get_data(chat=message.chat.id)
    order = OrderInfo(**data['order'])

    poll_message_id = data['poll_message_id']
    poll = await bot.stop_poll(message.chat.id, poll_message_id)

    poll.options.sort(key=lambda o: o.voter_count, reverse=True)

    if len(poll.options) > 1 and poll.options[0].voter_count == poll.options[1].voter_count:
        top_options = filter(lambda o: o.voter_count == poll.options[0].voter_count, poll.options)
        options = "\", \"".join(map(lambda o: o.text, top_options))
        question = "Из какого места заказать еду?"
        message_text = f"Варианты \"{options}\" набрали наибольшее количество голосов. " \
                       "Необходимо провести повторное голосование."
        await bot.send_message(message.chat.id, message_text)
        sent_message = await bot.send_poll(message.chat.id, question, order.places, None, None)
        await storage.update_data(chat=message.chat.id, data={'poll_message_id': sent_message.message_id})
        return

    winner_option = poll.options[0]
    order.chosen_place = winner_option.text

    inline_button_text = "Принять участие в формировании заказа"
    inline_button_data = str(message.chat.id)

    keyboard_markup = InlineKeyboardMarkup()
    keyboard_markup.add(
        InlineKeyboardButton(inline_button_text, callback_data=inline_button_data)
    )

    message_text = f"Вариант \"{winner_option.text}\" набрал наибольшее количество голосов."
    await bot.send_message(message.chat.id, message_text, reply_markup=keyboard_markup)

    await storage.set_state(chat=message.chat.id, state=ChatState.making_order)

    data = await storage.get_data(chat=message.chat.id)
    data['order'] = OrderInfo.as_dict(order)
    if 'poll_message_id' in data:
        data.pop('poll_message_id')
    await storage.set_data(chat=message.chat.id, data=data)
