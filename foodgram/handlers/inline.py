import hashlib

from aiogram.types import InputTextMessageContent, InlineQueryResultArticle

from .. import bot, dp, db_storage
from ..model.state import UserState, ChatState


@dp.inline_handler(lambda query: query.query.startswith('/add'), state="*")
async def inline(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    if parts[0] == '/addplace':
        options = await db_storage.get_places(inline_query.from_user.id)
        command = 'addplace'
        if not options:
            options = [
                "Теремок. Блины", "Макдоналдс", "Бургер Кинг",
                "Баскин Роббинс", "Буше торты", "Bekitzer Бекицер",
                "Crispy Pizza", "Чебуречная Брынза", "Таверна Сиртаки", "Суши-бар Кидо"
            ]
    else:
        options = await db_storage.get_dishes(inline_query.from_user.id)
        command = 'add'
    if len(parts) < 2:
        input_list = make_input_list(options, command)
    else:
        input_list = make_input_list(find_by_prefix(options, parts[1]), command)
    await bot.answer_inline_query(inline_query.id, results=input_list, cache_time=1)


@dp.inline_handler(lambda query: query.query.startswith('/delete'), state='*')
async def inline_delete(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    data = await db_storage.get_data(user=inline_query.from_user.id)
    lst = set(data.get('dishes', []))
    command = 'delete'
    if len(parts) < 2:
        input_list = make_input_list(lst, command)
    else:
        input_list = make_input_list(find_by_prefix(lst, parts[1]), command)
    await bot.answer_inline_query(inline_query.id, results=input_list, cache_time=1)


@dp.inline_handler(lambda query: query.query.startswith('/take'), state="*")
async def inline_add_to_bill(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    user_data = await db_storage.get_data(user=inline_query.from_user.id)
    data = await db_storage.get_data(chat=user_data['order_chat_id'])
    lst = []
    for item in data['matched_bill']['other']:
        lst.append(item['name'])
    command = 'take'
    if len(parts) < 2:
        input_list = make_input_list(lst, command)
    else:
        input_list = make_input_list(find_by_prefix(lst, parts[1]), command)
    await bot.answer_inline_query(inline_query.id, results=input_list, cache_time=1)


@dp.inline_handler(lambda query: query.query.startswith('/drop'), state="*")
async def inline_add_to_bill(inline_query):
    parts = inline_query.query.split(' ', maxsplit=1)
    user_data = await db_storage.get_data(user=inline_query.from_user.id)
    data = await db_storage.get_data(chat=user_data['order_chat_id'])
    lst = []
    for person in data['matched_bill']['matched']:
        if person['user_id'] == inline_query.from_user.id:
            for item in person['items']:
                lst.append(item['name'])
    command = 'drop'
    if len(parts) < 2:
        input_list = make_input_list(lst, command)
    else:
        input_list = make_input_list(find_by_prefix(lst, parts[1]), command)
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
