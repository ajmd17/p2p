class InvalidMessage(Exception):
    def __init__(self, msg):
        self.msg = "Invalid message: {}".format(msg)