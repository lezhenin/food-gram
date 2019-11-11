from collections import namedtuple


class OrderInfo(namedtuple("OrderInfo", [
    "chat_id",
    "owner_user_id",
    "owner_user_name",
    "places"
])):

    def add_place(self, new_place):
        if new_place not in self.places:
            self.places.append(new_place)

    def to_dict(self):
        return self._asdict()

    @staticmethod
    def from_dict(d):
        return OrderInfo(**d)

    @staticmethod
    def from_message(message):
        return OrderInfo(
            chat_id=message.chat.id,
            owner_user_id=message.from_user.id,
            owner_user_name=message.from_user.first_name,
            places=[],
        )
