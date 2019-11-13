import requests
from pyzbar.pyzbar import decode
from PIL import Image
import io


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


async def qr_decode(message, bot, API_TOKEN):
    file_id = message.photo[len(message.photo) - 1].file_id
    site = 'https://api.telegram.org/bot' \
           + API_TOKEN + '/getFile?file_id=' \
           + file_id
    gf = requests.get(site)
    site2 = 'https://api.telegram.org/file/bot' \
            + API_TOKEN + '/' + gf.json()['result']['file_path']
    df = requests.get(site2)
    image = Image.open(io.BytesIO(df.content))
    qr_txt = decode(image)
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