from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

from orderinfo import OrderInfo

import requests
import random
from pyzbar.pyzbar import decode
from PIL import Image


# токен  бота
API_TOKEN = '1056772125:AAFQrxSVgSzMO3Ihc9Rb3n4Uqm9pYZAa5NQ'
# создание бота и диспетчера
bot = Bot(token=API_TOKEN)
bot.parse_mode = 'HTML'
dp = Dispatcher(bot)

# order_chats[id чатa заказа][id того кто заказывает]=что он заказывает
order_chats = {}  # все чаты которые делают заказ
starter = {}  # те кто начинают чат (класс OrderInfo)
# массивы выше мб можно объединить (по сути - это в бд поэтому не важно как оно здесь)

# костыли:
order_enable = 0
photo_enable = 0

# kod[chat_id] = n-значный код?
kod = {}

# обработчик команды /start
@dp.message_handler(commands=['start'])
async def if_start(message: types.Message):

    global order_chats

    # если старт пишешь в личку боту
    if message.chat.type == 'private':
        message_text = "%s, привет. " \
                       "Команда /help поможет разобраться как что работает" % message.from_user.first_name
        await bot.send_message(message.chat.id, message_text)
        return

    # когда старт был нажат уже кем-то
    if message.chat.id in order_chats:
        message_text = "%s! Заказ уже делается! Не хулигань. 😠" % message.from_user.first_name
        await bot.send_message(message.chat.id, message_text)
        return

    # при первом старте запоминаем чат, назначаем главного
    order_chats[message.chat.id] = {}
    starter[message.chat.id] = OrderInfo(message) # пока не используется, потом
    message_text = "Привет, будем заказывать\n" \
                   "<b>%s</b> - инициатор заказа, будет иметь основные права и обязанности. " \
                   "Пишите места командой" % message.from_user.first_name
    await bot.send_message(message.chat.id, message_text)

    # информируем главного что он главный
    message_text = "Привет, %s! Ты решил сделать заказ в чате %s \n 😎 " % (message.from_user.first_name, message.chat.title)
    await bot.send_message(message.from_user.id, message_text)

    # генерируем код
    kod[message.chat.id] = random.randint(1000, 9999)  # пока не используется, потом


# обработчик команды /makeorder
@dp.message_handler(commands=['makeorder'])
async def if_makeorder(message: types.Message):

    global order_chats

    # польз-ль уже жал makeorder
    if message.from_user.id in order_chats[message.chat.id]:
        await bot.send_message(message.from_user.id, 'Заказывай же!')
        return

    # запоминаем того кто заказывает
    order_chats[message.chat.id][message.from_user.id] = {}
    message_text = "<b>%s</b> делает заказ" % message.from_user.first_name
    await bot.send_message(message.chat.id, message_text)
    message_text = "Заказ через команду /eat. " \
                "Уникальный код чата %s" % kod[message.chat.id]
    await bot.send_message(message.from_user.id, message_text)


# обработчик команды /eat & /bill
@dp.message_handler(content_types=['text'])
async def if_message(message: types.Message):

    global order_chats
    global order_enable
    global photo_enable

    # командой eat разрешаем ввод заказа текстом
    if message.text == '/eat':
        # проверка что пользователь регистрировался в чате - жал makeorder
        for i in order_chats:
            if message.from_user.id in order_chats[i]:
                order_enable = 1
                await bot.send_message(message.from_user.id, 'Пиши пункты заказа через перенос')
                return
        # если не нашли пользователя в массиве
        await bot.send_message(message.from_user.id, "Вас нет в списках! Жмите makeorder в чате заказа")
        return

    # командой bill разрешаем отправку фото
    elif message.text == '/bill':
        photo_enable = 1
        await bot.send_message(message.from_user.id, 'Отправь фото чека\nФото должно быть четким')

        # если просто текст поступил с разрешенным txt_enable
    else:
        if order_enable:
            order_enable = 0
            tmp = 0
            for i in order_chats:
                if message.from_user.id in order_chats[i]:
                    tmp = i
                    break
            for i in range(len(message.text.split())):
                order_chats[tmp][message.from_user.id][i] = message.text.split()[i]
            to_out = []
            for i in order_chats[tmp][message.from_user.id]:
                to_out.append('<b>' + str(i) + '</b> - ' + str(order_chats[tmp][message.from_user.id][i]))
            await bot.send_message(message.from_user.id, "\n".join(to_out))
        else:
            await bot.send_message(message.from_user.id, "/help  ⬅  жми")



def bill_existing(fn, fd, fpd, date, sum):
    site = 'https://proverkacheka.nalog.ru:9999/v1/ofds/*/inns/*/fss/'\
           + fn + '/operations/1/tickets/' + fd
    payload = {'fiscalSign': fpd, 'date': date, 'sum': sum}
    response = requests.get(site, params=payload)
    if response.status_code == 204:
        return 1 # чек есть в бд
    if response.status_code == 406:
        return 0 # чека нет или дата/сумма некорректная
    if response.status_code == 400:
        return -1  # неправильный запрос
    return -2 # просто ошибка


def bill_detal_inf(fn, fd, fpd):
    site = 'https://proverkacheka.nalog.ru:9999/v1/inns/*/kkts/*/fss/'\
           + fn + '/tickets/' + fd
    payload = {'fiscalSign': fpd, 'sendToEmail': 'no'}
    headers = {'device-id': '', 'device-os': '', 'Authorization': 'Basic Kzc5MTE5OTEyOTcxOjQ1ODQzMw=='}
    response = requests.get(site, params=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    #else:
    #    return -1
    return -1


@dp.message_handler(content_types=['photo'])
async def handle_docs_photo(message):
    global photo_enable
    if photo_enable:
        try:
            file_id = message.photo[len(message.photo)-1].file_id
            site = 'https://api.telegram.org/bot' \
                   + API_TOKEN + '/getFile?file_id=' \
                   + file_id
            gf = requests.get(site)
            site2 = 'https://api.telegram.org/file/bot'\
                    + API_TOKEN + '/'+ gf.json()['result']['file_path']
            df = requests.get(site2)
            with open(file_id+'.jpg', 'wb') as new_file:
                new_file.write(df.content)
            # os.startfile(r'ph1.jpg')
            qr_txt = decode(Image.open(file_id+'.jpg'))
            bill_par = {}
            bill_arr = str(qr_txt[0].data).replace("b'", '').split('&')
            for a in bill_arr:
                tmp = a.split('=')
                bill_par[tmp[0]] = tmp[1]
            # print(bill_par)

            a = bill_existing(bill_par['fn'], bill_par['i'], bill_par['fp'], bill_par['t'],
            bill_par['s'].replace(".", ""))
            if a:
                await bot.send_message(message.chat.id, 'Чек корректен')
            else:
                await bot.send_message(message.chat.id, str(a))
            ret = bill_detal_inf(bill_par['fn'], bill_par['i'], bill_par['fp'])
            to_out = []
            for i in ret['document']['receipt']['items']:
                to_out.append(i['name'] + '\n<i>Стоймсть:</i> <b>' + str(i['price'] / 100) + '</b>\n')
            await bot.send_message(message.chat.id, ''.join(to_out), parse_mode="HTML")
        except Exception as e:
            await bot.send_message(message.chat.id, e)
    else:
        await bot.send_message(message.chat.id, 'К чему ты это?', reply_to_message_id=message)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)