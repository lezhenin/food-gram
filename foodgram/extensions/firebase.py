import typing

from concurrent.futures import ThreadPoolExecutor

from aiogram.dispatcher.storage import BaseStorage

from ..utils import concurrent


class FirebaseStorage(BaseStorage):
    def __init__(self, creds):
        import firebase_admin
        from firebase_admin import credentials
        from firebase_admin import firestore

        firebase_admin.initialize_app(
            credentials.Certificate(creds)
        )
        self.client = firestore.client()
        self.executor = ThreadPoolExecutor(max_workers=1)

    def resolve_document(self, collection, chat, user):
        chat_id, user_id = map(str, self.check_address(chat=chat, user=user))
        document = self.client.document(f'{collection}/{chat_id}+{user_id}')
        if not document.get().exists:
            document.create({'state': None} if collection == 'state' else {})
        return document

    async def close(self):
        self.executor.shutdown()

    async def wait_closed(self):
        pass

    async def set_state(self, *,
                        chat: typing.Union[str, int, None] = None,
                        user: typing.Union[str, int, None] = None,
                        state: typing.Optional[typing.AnyStr] = None):

        def task():
            document = self.resolve_document('state', chat, user)
            document.set({'state': state})

        await concurrent.run_blocking(task, executor=self.executor)

    async def get_state(self, *,
                        chat: typing.Union[str, int, None] = None,
                        user: typing.Union[str, int, None] = None,
                        default: typing.Optional[str] = None) -> typing.Optional[str]:

        def task():
            document = self.resolve_document('state', chat, user)
            return document.get().to_dict()['state']

        return await concurrent.run_blocking(task, executor=self.executor)

    async def reset_state(self, *,
                          chat: typing.Union[str, int, None] = None,
                          user: typing.Union[str, int, None] = None,
                          with_data: typing.Optional[bool] = True):
        def task():
            document = self.resolve_document('state', chat, user)
            document.delete()
            if with_data:
                document = self.resolve_document('data', chat, user)
                document.delete()

        await concurrent.run_blocking(task, executor=self.executor)

    async def set_data(self, *,
                       chat: typing.Union[str, int, None] = None,
                       user: typing.Union[str, int, None] = None,
                       data: typing.Dict = None):

        def task():
            document = self.resolve_document('data', chat, user)
            document.set(data)

        await concurrent.run_blocking(task, executor=self.executor)

    async def get_data(self, *,
                       chat: typing.Union[str, int, None] = None,
                       user: typing.Union[str, int, None] = None,
                       default: typing.Optional[typing.Dict] = None) -> typing.Dict:
        def task():
            document = self.resolve_document('data', chat, user)
            return document.get().to_dict()

        return await concurrent.run_blocking(task, executor=self.executor)

    async def update_data(self, *,
                          chat: typing.Union[str, int, None] = None,
                          user: typing.Union[str, int, None] = None,
                          data: typing.Dict = None, **kwargs):
        def task():
            local_data = {} if data is None else data
            document = self.resolve_document('data', chat, user)
            new_data = document.get().to_dict()
            new_data.update(local_data, **kwargs)
            document.set(new_data)

        await concurrent.run_blocking(task, executor=self.executor)

    async def reset_data(self, *,
                         chat: typing.Union[str, int, None] = None,
                         user: typing.Union[str, int, None] = None):
        def task():
            document = self.resolve_document('data', chat, user)
            document.delete()

        await concurrent.run_blocking(task, executor=self.executor)

    async def set_bucket(self, *,
                         chat: typing.Union[str, int, None] = None,
                         user: typing.Union[str, int, None] = None,
                         bucket: typing.Dict = None):

        def task():
            document = self.resolve_document('bucket', chat, user)
            document.set(bucket)

        await concurrent.run_blocking(task, executor=self.executor)

    async def get_bucket(self, *,
                         chat: typing.Union[str, int, None] = None,
                         user: typing.Union[str, int, None] = None,
                         default: typing.Optional[dict] = None) -> typing.Dict:

        def task():
            document = self.resolve_document('bucket', chat, user)
            return document.get().to_dict()

        return await concurrent.run_blocking(task, executor=self.executor)

    async def update_bucket(self, *,
                            chat: typing.Union[str, int, None] = None,
                            user: typing.Union[str, int, None] = None,
                            bucket: typing.Dict = None, **kwargs):

        def task():
            local_data = {} if bucket is None else bucket
            document = self.resolve_document('bucket', chat, user)
            new_data = document.get().to_dict()
            new_data.update(local_data, **kwargs)
            document.set(new_data)

        await concurrent.run_blocking(task, executor=self.executor)

    async def reset_bucket(self, *,
                           chat: typing.Union[str, int, None] = None,
                           user: typing.Union[str, int, None] = None):

        def task():
            document = self.resolve_document('bucket', chat, user)
            document.delete()

        await concurrent.run_blocking(task, executor=self.executor)

    async def add_stats(self, stats: typing.Dict):

        def task():
            collection = self.client.collection('stats')
            collection.add(stats)

        await concurrent.run_blocking(task, executor=self.executor)

    async def get_dishes(self, user, date_from=None):

        def task():
            inline_dishes = []
            for order in self._get_stats_collection(['participants', 'dishes'], date_from).stream():
                for participant in filter(lambda x: x['user_id'] == user, list(order.get('participants'))):
                    inline_dishes.extend(participant['dishes'])
            return list(set(inline_dishes))

        return await concurrent.run_blocking(task, executor=self.executor)

    async def get_places(self, user, date_from=None):
        def task():
            inline_places = []
            for order in self._get_stats_collection(['participants', 'suggested_places'], date_from).stream():
                if list(filter(lambda x: x['user_id'] == user, list(order.get('participants')))):
                    inline_places.extend(order.get('suggested_places'))
            return list(set(inline_places))

        return await concurrent.run_blocking(task, executor=self.executor)

    def _get_stats_collection(self, fields=None, date_from=None):
        order_collection = self.client.collection('stats')
        if date_from is not None:
            order_collection = order_collection.where('date_started', '>', date_from)
        if fields is not None:
            order_collection = order_collection.select(fields)
        return order_collection
