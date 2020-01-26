import hashlib

from datetime import datetime, timedelta

from aiogram.types import InputTextMessageContent, InlineQueryResultArticle

from .. import bot, dp, db_storage
from ..model.state import UserState


@dp.inline_handler(lambda query: query.query.startswith('/add'), state="*")
async def inline(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    if (parts[0] == '/addplace'):
        lst = db_storage.get_places(inline_query.from_user.id)
        comand = 'addplace'
        if lst == []:
            lst = ["Теремок. Блины", "Макдоналдс", "Бургер Кинг", "Баскин Роббинс", "Буше торты", "Bekitzer Бекицер", "Crispy Pizza", "Чебуречная Брынза", "Таверна Сиртаки", "Суши-бар Кидо"]
    else:
        lst = db_storage.get_dishes(inline_query.from_user.id)
        comand = 'add'
    inpLst = []
    if len(parts) < 2:
        inpLst = make_input_list(lst, comand)
    else:
        inpLst = make_input_list(find_by_prefix(lst, parts[1]), comand)
    await bot.answer_inline_query(inline_query.id, results=inpLst, cache_time=1)

@dp.inline_handler(lambda query: query.query.startswith('/delete'), state=[UserState.making_order,UserState.finish_order])
async def inline_delete(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    data = await db_storage.get_data(user=inline_query.from_user.id)
    lst = set(data.get('dishes', []))
    comand = 'delete'
    inpLst = []
    if len(parts) < 2:
        inpLst = make_input_list(lst, comand)
    else:
        inpLst = make_input_list(find_by_prefix(lst, parts[1]), comand)
    await bot.answer_inline_query(inline_query.id, results=inpLst, cache_time=1)

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
