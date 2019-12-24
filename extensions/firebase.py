import typing

from aiogram.dispatcher.storage import BaseStorage


class FirebaseStorage(BaseStorage):
    def __init__(self, creds):
        import firebase_admin
        from firebase_admin import credentials
        from firebase_admin import firestore

        firebase_admin.initialize_app(
            credentials.Certificate(creds)
        )
        self.client = firestore.client()

    def resolve_document(self, collection, chat, user):
        chat_id, user_id = map(str, self.check_address(chat=chat, user=user))
        document = self.client.document(f'{collection}/{chat_id}+{user_id}')
        if not document.get().exists:
            document.create({'state': None} if collection == 'state' else {})
        return document

    async def close(self):
        pass

    async def wait_closed(self):
        pass

    async def set_state(self, *,
                        chat: typing.Union[str, int, None] = None,
                        user: typing.Union[str, int, None] = None,
                        state: typing.Optional[typing.AnyStr] = None):
        document = self.resolve_document('state', chat, user)
        document.set({'state': state})

    async def get_state(self, *,
                        chat: typing.Union[str, int, None] = None,
                        user: typing.Union[str, int, None] = None,
                        default: typing.Optional[str] = None) -> typing.Optional[str]:
        document = self.resolve_document('state', chat, user)
        return document.get().to_dict()['state']

    async def reset_state(self, *,
                          chat: typing.Union[str, int, None] = None,
                          user: typing.Union[str, int, None] = None,
                          with_data: typing.Optional[bool] = True):
        document = self.resolve_document('state', chat, user)
        document.delete()
        if with_data:
            document = self.resolve_document('data', chat, user)
            document.delete()

    async def set_data(self, *,
                       chat: typing.Union[str, int, None] = None,
                       user: typing.Union[str, int, None] = None,
                       data: typing.Dict = None):
        document = self.resolve_document('data', chat, user)
        document.set(data)
        print(data)


    async def get_data(self, *,
                       chat: typing.Union[str, int, None] = None,
                       user: typing.Union[str, int, None] = None,
                       default: typing.Optional[typing.Dict] = None) -> typing.Dict:
        document = self.resolve_document('data', chat, user)
        return document.get().to_dict()

    async def update_data(self, *,
                          chat: typing.Union[str, int, None] = None,
                          user: typing.Union[str, int, None] = None,
                          data: typing.Dict = None, **kwargs):
        if data is None:
            data = {}
        document = self.resolve_document('data', chat, user)
        new_data = document.get().to_dict()
        new_data.update(data, **kwargs)
        document.set(new_data)

    async def reset_data(self, *,
                         chat: typing.Union[str, int, None] = None,
                         user: typing.Union[str, int, None] = None):
        document = self.resolve_document('data', chat, user)
        document.delete()

    async def set_bucket(self, *,
                         chat: typing.Union[str, int, None] = None,
                         user: typing.Union[str, int, None] = None,
                         bucket: typing.Dict = None):
        document = self.resolve_document('bucket', chat, user)
        document.set(bucket)

    async def get_bucket(self, *,
                         chat: typing.Union[str, int, None] = None,
                         user: typing.Union[str, int, None] = None,
                         default: typing.Optional[dict] = None) -> typing.Dict:
        document = self.resolve_document('bucket', chat, user)
        return document.get().to_dict()

    async def update_bucket(self, *,
                            chat: typing.Union[str, int, None] = None,
                            user: typing.Union[str, int, None] = None,
                            bucket: typing.Dict = None, **kwargs):
        if bucket is None:
            bucket = {}
        document = self.resolve_document('bucket', chat, user)
        new_bucket = document.get().to_dict()
        new_bucket.update(bucket, **kwargs)
        document.set(new_bucket)

    async def reset_bucket(self, *,
                           chat: typing.Union[str, int, None] = None,
                           user: typing.Union[str, int, None] = None):
        document = self.resolve_document('bucket', chat, user)
        document.delete()
