FROM python:3.7

ADD ./foodgram /bot/foodgram
ADD ./requirements.txt /bot

WORKDIR /bot

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT python -m foodgram
