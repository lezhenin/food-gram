from environs import Env

env = Env()

env.read_env()

with env.prefixed('FOODGRAM_'):

    BOT_API_TOKEN = env.str('BOT_API_TOKEN')

    FIREBASE_CREDENTIALS = env.json('FIREBASE_CREDENTIALS')

    STATISTICS_SERVICE_BASE_URL = env.str('STATISTICS_SERVICE_BASE_URL')

    BILL_DATABASE_URL = env.str('BILL_DATABASE_URL')
    BILL_DATABASE_PASSWORD = env.str('BILL_DATABASE_PASSWORD')
