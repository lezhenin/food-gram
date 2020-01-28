import secrets
import hashlib

import requests_async as requests

from ..model.orderinfo import OrderInfo
from ..config import STATISTICS_SERVICE_BASE_URL


async def get_chat_url(chat_id):
    action = f'chat/{chat_id}'
    token, digest = generate_token()
    await send_digest(digest, action)
    return f'{STATISTICS_SERVICE_BASE_URL}/{action}'


def get_user_url(user_id):
    action = f'user/{user_id}'
    token, digest = generate_token()
    await send_digest(digest, action)
    return f'{STATISTICS_SERVICE_BASE_URL}/{action}?token={token}'


def generate_token():
    token = secrets.token_hex(16)
    digest = hashlib.sha256().update(token).hexdigest()
    return token, digest


async def send_digest(digest, action):
    url = f'{STATISTICS_SERVICE_BASE_URL}/auth'
    params = {'hash': digest, 'action': action}
    await requests.post(url, params=params)


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
        'sum': order.price,
        'participants': participants
    }
