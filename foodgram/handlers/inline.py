import hashlib

from datetime import datetime, timedelta

from aiogram.types import InputTextMessageContent, InlineQueryResultArticle

from .. import bot, dp, db_storage
from ..model.state import UserState


@dp.inline_handler(lambda query: query.query.startswith('/add'), state=UserState.making_order)
async def inline_dishes(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    dishes = db_storage.get_dishes(inline_query.from_user.id, date_from)

    if len(parts) < 2:
        input_list = make_input_list(dishes, 'add')
    else:
        input_list = make_input_list(find_by_prefix(dishes, parts[1]), 'add')

    await bot.answer_inline_query(inline_query.id, results=input_list, cache_time=1)


@dp.inline_handler(lambda query: query.query.startswith('/addplace'))
async def inline_places(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    places = db_storage.get_places(inline_query.from_user.id, date_from)
    if not places:
        places = [
            "Теремок. Блины", "Макдоналдс", "Бургер Кинг",
            "Баскин Роббинс", "Буше торты", "Bekitzer Бекицер",
            "Crispy Pizza", "Чебуречная Брынза", "Таверна Сиртаки", "Суши-бар Кидо"
        ]

    if len(parts) < 2:
        input_list = make_input_list(places, 'addplace')
    else:
        input_list = make_input_list(find_by_prefix(places, parts[1]), 'addplace')

    await bot.answer_inline_query(inline_query.id, results=input_list, cache_time=1)


def make_input_list(items, command):
    input_list = list(map(lambda item: InlineQueryResultArticle(
        id=hashlib.md5(item.encode()).hexdigest(),
        title=item,
        input_message_content=InputTextMessageContent(f'/{command} {item}')
    ), items))
    return input_list


def find_by_prefix(strings, prefix):
    return list(
        filter(
            lambda place: place.lower().startswith(prefix.lower()),
            strings
        )
    )
