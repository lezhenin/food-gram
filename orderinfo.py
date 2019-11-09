
class OrderInfo:

    def __init__(self, msg=None):
        if msg is None:
            self.user_id = None
            self.cid = None
            self.ufn = None
            self.usn = None
        else:
            self.cid = msg.from_user.id
            self.user_id = msg.chat.id
            self.ufn = msg.from_user.first_name
            self.usn = msg.from_user.first_name
        return
