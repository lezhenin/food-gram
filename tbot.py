# импорт библиотек
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

import requests
import random
from pyzbar.pyzbar import decode
from PIL import Image
# токен  бота
API_TOKEN = '1056772125:AAFQrxSVgSzMO3Ihc9Rb3n4Uqm9pYZAa5NQ'

# создание бота и диспетчера
bot = Bot(token = API_TOKEN)
bot.parse_mode = 'HTML'
dp = Dispatcher(bot)


# master_name - тот кто спровоцировал заказ (start)
global order_info
order_info = {'chat_id': '', 'master_name': '', 'master_id': ''}


global orders # заказы польз-й через makeorder
orders = {}
# бот запущен = 1 иначе 0 - нужно для проверки ниже
global txt_en
txt_en = 0

firebase_admin.initialize_app(
    credentials.Certificate('credentials.json')
)
db = firestore.client()


#разрешить отпраить фото
global ph_enable
ph_enable = 0

def get_inf(what):  # для получения...
    MethodGetUpdates = 'https://api.telegram.org/bot{token}/getUpdates'.format(token=API_TOKEN)
    response = requests.post(MethodGetUpdates)
    results = response.json()
    if what == 'user_id':  #...id пользователя
        print(results)
        return results['result'][0]['message']['from']['id']
    if what == 'chat_id': #...id чата
        return results['result'][0]['message']['chat']['id']
    if what == 'user_name':    #...имени пользователя
        return results['result'][0]['message']['from']['first_name']
    if what == 'chat_name':  # ...имени чата
        return results['result'][0]['message']['chat']['title'] \
               or results['result'][0]['message']['chat']['first_name']
    return -1


def init(): # инициализация структуры при старте
    if '' not in order_info.values(): # если уже был заказ, поля непустые
        return 0
    order_info['master_id'] = get_inf('user_id')
    order_info['master_name'] = get_inf('user_name')
    order_info['chat_id'] = get_inf('chat_id')
    if -1 in order_info.values(): # если была ошибка получения инф-ии
        return 0
    return 1


# обработик команды /start
@dp.message_handler(commands=['start'])
async def if_start(message: types.Message):

    if init(): # если заказ начинается, иниц-м главного заказчика и чат заказа
        await bot.send_message(order_info['chat_id'], "Привет, будем заказывать\n<b>"\
                               + str(order_info['master_name'])\
                               + "</b> - инициатор заказа, будет иметь основные права и обязанности. Пишите места командой")
        await bot.send_message(order_info['master_id'], "Привет, " + str(order_info['master_name']) \
                               + " Ты решил сделать заказ в чате " + get_inf('chat_name') +" 😎 ")
    else: # если заказ начат
        await bot.send_message(order_info['chat_id'], get_inf('user_name')\
                               + '! Заказ уже делается! Не хулигань. 😠')

    some_data = {'event': 'send_start_message', 'user_id': message.from_user.id, 'message_id': message.message_id}
    db.collection('events').add(some_data)
    await bot.send_message(get_id(), "Привет!\nПомогу тебе и твоей группе упростить процесс заказа.")




@dp.message_handler(commands=['makeorder'])
async def if_makeorder(message: types.Message):
    id_tmp = get_inf('user_id')
    chat_tmp = get_inf('chat_id')
    # заказ уже кто-то начал => в словаре order_info не может быть '':
    if '' not in order_info.values():
        if id_tmp not in orders: # если юзер еще не делал заказ
            orders[id_tmp]={} # запоминаем тех кто заказывает
            await bot.send_message(chat_tmp, "<b>" +\
                                   get_inf('user_name') + "</b> делает заказ")
            await bot.send_message(message.from_user.id, "Заказ через команду /eat")
        else: # если юзер делал заказ
            await bot.send_message(message.from_user.id, 'Заказывай же!')
    else: # заказ net
        await bot.send_message(chat_tmp, 'Заказ еще не начат')

@dp.message_handler(content_types=['text'])
async def eat_message(msg: types.Message):
    global txt_en
    if msg.text == '/eat':
        txt_en = 1
        await bot.send_message(msg.from_user.id, 'Пиши пункты заказа через перенос')
        return
    elif msg.text == '/bill':
        global ph_enable
        ph_enable = 1
        await bot.send_message(msg.from_user.id, 'Отправь фото чека\nФото должно быть четким')
    else:
        if txt_en:
            txt_en = 0
            if get_inf('user_id') not in orders:
                await bot.send_message(msg.from_user.id, "Вас нет в списках! Жмите makeorder в чате заказа")
            else:
                tmp_id = get_inf('user_id')
                tmp_name = get_inf('user_name')
                orders[tmp_id][tmp_name] = {}
                for i in range(len(msg.text.split())):
                    orders[tmp_id][tmp_name][i] = msg.text.split()[i]
                to_out = []
                for i in orders[tmp_id][tmp_name]:
                    to_out.append('<b>'+str(i) + '</b> - ' + str(orders[tmp_id][tmp_name][i]))
                await bot.send_message(msg.from_user.id, "\n".join(to_out))








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
    global ph_enable
    if ph_enable:
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
    executor.start_polling(dp)
