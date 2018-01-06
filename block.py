import _strptime
import datetime
import time
import json

class Block:
    def __init__(self, blockid, timestamp, data, parent):
        self.blockid = blockid
        self.timestamp = timestamp
        self.data = data
        self.parent = parent

    def __lt__(self, blk):
        return self.blockid < blk.blockid

    def __gt__(self, blk):
        return self.blockid > blk.blockid

    def isgenesis(self):
        return self.blockid == 0

    def serialize_json(self):
        return json.dumps(self.serialize_obj())

    def serialize_obj(self):
        return {
            'blockid': self.blockid,
            'timestamp': self.timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
            'data': self.data,
            'parent': self.parent
        }

    @classmethod
    def deserialize_json(cls, data):
        return cls.deserialize_obj(json.loads(data))

    @classmethod
    def deserialize_obj(cls, obj):
        assert obj['blockid'] is not None
        assert obj['timestamp'] is not None
        assert obj['data'] is not None

        obj['timestamp'] = datetime.datetime.strptime(obj['timestamp'], "%Y-%m-%dT%H:%M:%S")

        return Block(blockid=int(obj['blockid']), timestamp=obj['timestamp'], data=obj['data'], parent=obj['parent'])

    def savelocal(self):
        f = open('./data/blk/blk-{}.dat'.format(self.blockid), 'w+')
        f.write(self.serialize_json())


class Transaction(Block):
    def __init__(self, blockid, timestamp, senderid, receiverid, amt, parent):
        Block.__init__(self, blockid, timestamp, { 'sender': senderid, 'receiver': receiverid, 'amt': amt }, parent)

    @classmethod
    def deserialize_obj(cls, obj):
        assert obj['blockid'] is not None
        assert obj['timestamp'] is not None
        assert obj['data'] is not None
        assert obj['data']['sender'] is not None
        assert isinstance(obj['data']['sender'], basestring)
        assert obj['data']['receiver'] is not None
        assert isinstance(obj['data']['receiver'], basestring)
        assert obj['data']['amt'] is not None
        assert isinstance(obj['data']['amt'], int)
        assert obj['data']['amt'] > 0

        obj['timestamp'] = datetime.datetime.strptime(obj['timestamp'], "%Y-%m-%dT%H:%M:%S")

        return Transaction(blockid=int(obj['blockid']), timestamp=obj['timestamp'], senderid=obj['data']['sender'], receiverid=obj['data']['receiver'], amt=obj['data']['amt'], parent=obj['parent'])


    def savelocal(self):
        f = open('./data/tx/tx-{}.dat'.format(self.blockid), 'w+')
        f.write(self.serialize_json())

GENESISTX = Transaction(
    blockid=0,
    timestamp=datetime.datetime(2018, 1, 1),
    senderid='0x0',
    receiverid='0x0',
    amt=100000000,
    parent=None
)