class InvalidMessage(Exception):
    def __init__(self, msg):
        super(InvalidMessage, self).__init__("Invalid message: {}".format(msg))