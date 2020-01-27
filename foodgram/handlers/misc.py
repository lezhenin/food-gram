from aiogram.types import Message

from .. import bot, dp
from ..utils import stats


@dp.message_handler(commands=['stats'], state='*')
async def if_stats(message: Message):
    if message.chat.type == 'private':
        stats_url = stats.get_user_url(message.chat.id)
    elif message.chat.type == 'group':
        stats_url = stats.get_chat_url(message.chat.id)
    else:
        return

    message_text = f'Ваша статистика доступна по ссылке {message.link(stats_url)}'
    await bot.send_message(message.chat.id, message_text)


@dp.message_handler(commands=['start'], chat_type='private')
async def if_start_in_private(message: Message):
    if message.chat.type == 'private':
        message_text = "%s, привет. " \
                       "Команда /help поможет разобраться как что работает" % message.from_user.first_name
        await bot.send_message(message.chat.id, message_text)
        return


@dp.message_handler(commands=['help'], state='*')
async def help_command(message):
    help_message = "Добавьте меня в беседу. Потом:\n" \
                   "Убедитесь, что у вас есть личный диалог с ботом\n" \
                   "/start - начать заказ. Нажавший - ответственный\n" \
                   "/addplace <место> - предложить место заказа для голосования\n" \
                   "/startpoll - начать голосование для выбора места заказа\n" \
                   "/finishpoll - завершить голосование\n" \
                   "/cancelorder - отмена заказа\n" \
                   "\nПосле выбора места можно делать заказ в личном диалоге с ботом:\n" \
                   "/add <блюдо> - добавить пункт заказа\n" \
                   "/change <номер\_блюда> <новое\_блюдо> - изменить пункт заказа\n" \
                   "/list - вывод пунктов заказа\n" \
                   "/finish - закончить формирование заказа\n" \
                   "/cancel - отказаться от участия в заказе\n" \
                   "/status - ответственному - проверить состояние заказа\n" \
                   "\nПосле выбора блюд ответственный завершает заказ в общем чате:\n" \
                   "/finishorder - закончить формирование заказа\n" \
                   "/closeorder - заказ выполнен\n" \
                   "\n/stats - получить ссылку для просмотра статистики\n"
    await bot.send_message(message.chat.id, help_message, parse_mode='Markdown')
