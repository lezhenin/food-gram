from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from .. import dp, bot, storage
from ..model.orderinfo import OrderInfo
from foodgram.model.state import UserState


def make_keyboard():
    add_button = InlineKeyboardButton("Добавить блюдо", switch_inline_query_current_chat='/add ')
    delete_button = InlineKeyboardButton("Удалить блюдо", switch_inline_query_current_chat='/delete ')
    keyboard_markup = InlineKeyboardMarkup()
    keyboard_markup.add(add_button, delete_button)
    return keyboard_markup


@dp.message_handler(
    commands=['add'], chat_type='private', state='*',
    user_state=[UserState.making_order, UserState.finish_order]
)
async def if_add_in_private(message: Message):
    dish = message.get_args()
    if not dish:
        return

    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    dishes.append(dish)

    await storage.update_data(user=message.from_user.id, data={'dishes': dishes})

    message_text = f"Блюдо \"{dish}\" добавлено."
    await bot.send_message(message.from_user.id, message_text, reply_markup=make_keyboard())


@dp.message_handler(
    commands=['delete'], regexp='/delete \\w+\\s*', chat_type='private',
    state='*', user_state=[UserState.making_order, UserState.finish_order]
)
async def if_delete_in_private(message: Message):
    dish = message.get_args()
    print(dish)
    if not dish:
        return

    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    if dish in dishes:
        index = dishes.index(dish)
        print(index)
        del dishes[index]
        await storage.update_data(user=message.from_user.id, data={'dishes': dishes})
        message_text = f"Блюдо \"{dish}\" удалено."
        await bot.send_message(message.from_user.id, message_text, reply_markup=make_keyboard())


@dp.message_handler(
    commands=['change'], regexp='/change \\d+ \\w+', chat_type='private', state='*',
    user_state=[UserState.making_order, UserState.finish_order]
)
async def if_change_in_private(message: Message):
    args = message.get_args()
    index, dish = args.split(' ', maxsplit=1)
    index = int(index)

    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    if index - 1 < len(dishes):
        dishes[index - 1] = dish
        await storage.update_data(user=message.from_user.id, data={'dishes': dishes})


@dp.message_handler(
    commands=['list'], chat_type='private', state='*',
    user_state=[UserState.making_order, UserState.finish_order]
)
async def if_list_in_private(message: Message):
    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    dishes = [str(i + 1) + '. ' + dishes[i] for i in range(len(dishes))]
    message_text = 'Блюда в заказе:\n' + '\n'.join(dishes) if (len(dishes) > 0) else 'Ваш заказ пуст'
    await bot.send_message(message.from_user.id, message_text, reply_markup=make_keyboard())


@dp.message_handler(
    commands=['finish'], chat_type='private', state='*',
    user_state=[UserState.making_order, UserState.finish_order]
)
async def if_finish_in_private(message: Message):
    data = await storage.get_data(user=message.from_user.id)
    dishes = data.get('dishes', [])
    dishes = [str(i + 1) + '. ' + dishes[i] for i in range(len(dishes))]
    if len(dishes) > 0:
        message_text = 'Заказ завершен. Блюда в заказе:\n' + '\n'.join(dishes)
        await storage.set_state(user=message.from_user.id, state=UserState.finish_order)
        await bot.send_message(message.from_user.id, message_text)
    else:
        message_text = 'Вы ничего не добавили в заказ. Вы можете отменить заказ командой /cancel'
        await bot.send_message(message.from_user.id, message_text, reply_markup=make_keyboard())


@dp.message_handler(
    commands=['status'], chat_type='private', is_order_owner=True, state='*'
)
async def if_status_in_private(message: Message):
    data = await storage.get_data(user=message.from_user.id)
    chat_id = data['owned_order_chat_id']
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


@dp.message_handler(
    commands=['cancel'], chat_type='private', state='*',
    user_state=[UserState.making_order, UserState.finish_order]
)
async def if_cancel_in_private(message: Message):
    data = await storage.get_data(user=message.from_user.id)
    chat_id = data['order_chat_id']
    chat = await bot.get_chat(chat_id=chat_id)
    await storage.reset_state(user=message.from_user.id, with_data=True)
    await storage.reset_state(chat=chat_id, user=message.from_user.id, with_data=True)
    data = await storage.get_data(chat=chat.id)
    order = OrderInfo(**data['order'])
    order.remove_participant(message.from_user.id)
    await storage.update_data(chat=chat.id, data={'order': OrderInfo.as_dict(order)})
    message_text = f'Ваш заказ в \"{chat.title}\" отменен.'
    await bot.send_message(message.from_user.id, message_text)




