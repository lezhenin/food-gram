from aiogram.dispatcher.filters import AbstractFilter

from aiogram.types import Message, CallbackQuery

"""
These filters currently work for messages and call back queries
"""


def unwrap_query(obj):
    if isinstance(obj, CallbackQuery):
        return obj
    else:
        return None


def unwrap_message(obj):
    if isinstance(obj, Message):
        return obj
    elif isinstance(obj, CallbackQuery) and obj.message:
        return obj.message
    else:
        return None


def get_user_id(obj):
    if isinstance(obj, Message):
        return obj.from_user.id
    elif isinstance(obj, CallbackQuery):
        return obj.from_user.id
    else:
        return None


def get_chat_id(obj):
    if isinstance(obj, Message):
        return obj.chat.id
    elif isinstance(obj, CallbackQuery) and obj.message:
        return obj.message.chat.id
    else:
        return None


def wrap_list(obj):
    if not isinstance(obj, (list, set, tuple, frozenset)):
        return [obj]
    return obj


class UserStateFilter(AbstractFilter):

    def __init__(self, dispatcher, user_state=None, user_state_not=None):

        if user_state is None and user_state_not is None:
            raise ValueError("user_state and user_state_not cannot be None simultaneously")

        if user_state is not None and user_state_not is not None:
            raise ValueError("user_state and user_state_not cannot be not None simultaneously")

        self.dispatcher = dispatcher

        self.all_pass = False
        if isinstance(user_state, str) and user_state == '*':
            self.all_pass = True

        self.negate = user_state_not is not None
        self.chat_states_to_check = wrap_list(user_state if not self.negate else user_state_not)

    @classmethod
    def validate(cls, full_config):
        result = {}

        if "user_state" in full_config:
            result["user_state"] = full_config.pop("user_state")

        if "user_state_not" in full_config:
            result["user_state_not"] = full_config.pop("user_state_not")

        return result

    async def check(self, obj):

        user_id = get_user_id(obj)
        if user_id is None:
            current_state = None
        else:
            current_state = await self.dispatcher.storage.get_state(user=user_id)

        if self.all_pass:
            return {'user_state': current_state}

        if current_state in self.chat_states_to_check and self.negate:
            return False

        if current_state not in self.chat_states_to_check and not self.negate:
            return False

        return {'user_state': current_state}


class ChatStateFilter(AbstractFilter):

    def __init__(self, dispatcher, chat_state=None, chat_state_not=None):

        if chat_state is None and chat_state_not is None:
            raise ValueError("chat_state and chat_state_not cannot be None simultaneously")

        if chat_state is not None and chat_state_not is not None:
            raise ValueError("chat_state and chat_state_not cannot be not None simultaneously")

        self.all_pass = False
        if isinstance(chat_state, str) and chat_state == '*':
            self.all_pass = True

        self.dispatcher = dispatcher
        self.negate = chat_state is None
        self.chat_states_to_check = wrap_list(chat_state if not self.negate else chat_state_not)

    @classmethod
    def validate(cls, full_config):
        result = {}

        if "chat_state" in full_config:
            result["chat_state"] = full_config.pop("chat_state")

        if "chat_state_not" in full_config:
            result["chat_state_not"] = full_config.pop("chat_state_not")

        return result

    async def check(self, obj):

        chat_id = get_chat_id(obj)

        if chat_id is None:
            current_state = None
        else:
            current_state = await self.dispatcher.storage.get_state(chat=chat_id, user=None)

        if self.all_pass:
            return {'chat_state': current_state}

        if current_state in self.chat_states_to_check and self.negate:
            return False

        if current_state not in self.chat_states_to_check and not self.negate:
            return False

        return {'chat_state': current_state}


class OrderOwnerFilter(AbstractFilter):

    def __init__(self, dispatcher, is_order_owner):

        if is_order_owner is False:
            raise ValueError("is_order_owner cannot be False")

        self.dispatcher = dispatcher

    @classmethod
    def validate(cls, full_config):
        result = {}
        if "is_order_owner" in full_config:
            result["is_order_owner"] = full_config.pop("is_order_owner")
        return result

    async def check(self, obj):
        message = unwrap_message(obj)
        if message is None:
            return False

        user_id = get_user_id(obj)
        if user_id is None:
            return False

        if message.chat.type == 'private':
            data = await self.dispatcher.storage.get_data(user=user_id)
            if 'owned_order_chat_id' not in data:
                return False
            chat_id = data['owned_order_chat_id']
        else:
            chat_id = message.chat.id

        data = await self.dispatcher.storage.get_data(chat=chat_id)

        if 'order' not in data:
            return False

        owner_user_id = data['order']['owner_user_id']
        return user_id == owner_user_id


class OrderParticipantFilter(AbstractFilter):

    def __init__(self, dispatcher, is_order_participant):
        if is_order_participant is False:
            raise ValueError("is_order_participant cannot be False")

        self.dispatcher = dispatcher

    @classmethod
    def validate(cls, full_config):
        result = {}
        if "is_order_participant" in full_config:
            result["is_order_participant"] = full_config.pop("is_order_participant")
        return result

    async def check(self, obj):
        message = unwrap_message(obj)
        if message is None:
            return False

        user_id = get_user_id(obj)
        if user_id is None:
            return False

        if message.chat.type == 'private':
            data = await self.dispatcher.storage.get_data(user=user_id)
            if 'order_chat_id' not in data:
                return False
            chat_id = data['order_chat_id']
        else:
            chat_id = message.chat.id

        data = await self.dispatcher.storage.get_data(chat=chat_id)

        if 'order' not in data:
            return False

        participants_user_ids = data['order']['participants']
        return user_id in participants_user_ids


class ChatTypeFilter(AbstractFilter):

    def __init__(self, chat_type):
        if chat_type is False:
            raise ValueError("chat_type cannot be False")

        self.expected_types = wrap_list(chat_type)

    @classmethod
    def validate(cls, full_config):
        result = {}
        if "chat_type" in full_config:
            result["chat_type"] = full_config.pop("chat_type")
        return result

    async def check(self, obj):
        message = unwrap_message(obj)
        if message is None:
            return False

        return message.chat.type in self.expected_types
