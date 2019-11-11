from collections import namedtuple

class OrderInfo:

    def __init__(
            self,
            chat_id,
            owner_user_id,
            owner_user_first_name,
            owner_user_last_name,
            places
    ):
        self.chat_id = chat_id
        self.owner_user_id = owner_user_id
        self.owner_user_first_name = owner_user_first_name
        self.owner_user_last_name = owner_user_last_name
        self.places = places

    def __str__(self):
        return f"order in chat {self.chat_id} owned by {self.owner_user_id}"

    @staticmethod
    def from_message(message):
        return OrderInfo(
            message.chat.id,
            message.from_user.id,
            message.from_user.first_name,
            message.from_user.last_name,
            places=[]
        )
