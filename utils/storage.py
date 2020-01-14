from orderinfo import OrderInfo


class OrderManger:
    def __init__(self, storage):
        self.storage = storage

    async def load(self, chat_id):
        data = await self.storage.get_data(chat=chat_id)
        return OrderInfo(**data['order'])

    async def save(self, order, chat_id):
        await self.storage.update_data(
            chat=chat_id, data={'order': OrderInfo.as_dict(order)}
        )

# class StateManger:
#     def __init__(self, storage):
#         self.storage = storage
#
#     async def get_state(self, chat_id=None, user_id=None):

