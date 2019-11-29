from dataclasses import dataclass
from dataclasses import asdict

import typing


@dataclass(init=True)
class OrderInfo:

    chat_id: int
    owner_user_id: int
    owner_user_name: int
    places: typing.List[str]
    participants: typing.List[int]

    def add_place(self, new_place):
        if new_place not in self.places:
            self.places.append(new_place)

    def add_participant(self, user_id):
        self.participants.append(int(user_id))

    @staticmethod
    def as_dict(order_info):
        return asdict(order_info)

    @staticmethod
    def from_message(message):
        return OrderInfo(
            chat_id=message.chat.id,
            owner_user_id=message.from_user.id,
            owner_user_name=message.from_user.first_name,
            places=[],
            participants=[]
        )
