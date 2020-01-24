from orderinfo import OrderInfo

STATS_URL = 'http://localhost:4200'


def get_chat_url(chat_id):
    return f'{STATS_URL}/chat/{chat_id}'


def get_user_url(user_id):
    return f'{STATS_URL}/user/{user_id}'


async def collect_data(bot, storage, chat_id):
    chat_data = await storage.get_data(chat=chat_id)
    order = OrderInfo(**chat_data['order'])

    chat = await bot.get_chat(chat_id)

    participants = []
    for user_id in order.participants:
        user_data = await storage.get_data(user=user_id)
        user = await bot.get_chat(chat_id=user_id)
        participants.append({
            'user_id': user.id,
            'username': user.username,
            'fullname': user.full_name,
            'dishes': user_data['dishes']
        })

    return {
        'chat_id': chat.id,
        'chat_name': chat.title,
        'date_started': order.date_started,
        'date_finished': order.date_finished,
        'date_delivered': order.date_delivered,
        'chosen_place': order.chosen_place,
        'suggested_places': order.places,
        'sum': 0,
        'participants': participants
    }
