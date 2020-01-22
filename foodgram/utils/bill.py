import logging
import requests_async as requests
from pyzbar.pyzbar import decode
from PIL import Image

from foodgram.utils.concurrent import run_blocking

BILL_DATABASE_URL = 'https://proverkacheka.nalog.ru:9999/v1'
PASSWORD = 'Kzc5MTE5OTEyOTcxOjQ1ODQzMw=='


async def is_bill_exist(bill):
    fn, fd, fpd = bill['fn'], bill['i'], bill['fp']
    date, sum = bill['t'],  bill['s'].replace('.', '')
    url = f'{BILL_DATABASE_URL}/ofds/*/inns/*/fss/{fn}/operations/1/tickets/{fd}'
    params = {'fiscalSign': fpd, 'date': date, 'sum': sum}
    response = await requests.get(url, params=params)
    logging.debug(f'Check is bill exists: response_code = {response.status_code}')
    return response.status_code == 204


async def get_bill_data(bill, retries=2):
    if not (await is_bill_exist(bill)):
        return None
    fn, fd, fpd = bill['fn'], bill['i'], bill['fp']
    url = f'{BILL_DATABASE_URL}/inns/*/kkts/*/fss/{fn}/tickets/{fd}'
    params = {'fiscalSign': fpd, 'sendToEmail': 'no'}
    headers = {'device-id': '', 'device-os': '', 'Authorization': f'Basic {PASSWORD}'}
    while True:
        logging.debug(f'Retrieve bill data: retries left = {retries}')
        response = await requests.get(url, params=params, headers=headers)
        logging.debug(f'Retrieve bill data: retries left = {retries - 1}, response_code = {response.status_code}')
        if response.status_code == 200:
            return response.json()
        retries -= 1
        if retries <= 0:
            return None


async def decode_qr_bill(image_bytes):
    image = Image.open(image_bytes)
    decoded = await run_blocking(decode, image)
    text = list(map(lambda d: d.data, decoded))
    bills = list(map(parse_qr_bill_text, text))
    return bills


def parse_qr_bill_text(qr_text):
    bill = {}
    params = str(qr_text).replace("b'", '').split('&')
    for entry in params:
        pair = entry.split('=')
        bill[pair[0]] = pair[1]
    return bill



