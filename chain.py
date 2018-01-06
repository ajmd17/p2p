import time
import os
import thread
import re
import sqlite3

from block import *

if not os.path.isdir('./data'):
    os.mkdir('./data')

# blocks_conn = sqlite3.connect('./data/blocks.db')
# blocks_cur = blocks_conn.cursor()

class Chain:
    def __init__(self, key):
        self.blocks = []
        self.key = key
        self.remote_diff = 0
        self.local_blocks_loaded = False

    def loadlocal(self, handlers):
        thread.start_new_thread(self._loadlocalloop, (handlers,))

    def _loadlocalloop(self, handlers):
        time.sleep(5)
        assert self.local_blocks_loaded == False

        k = self.key
        pth = './data/{}'.format(k)

        handlers['onstatus']('Loading local blocks in path "{}"...'.format(pth))

        if os.path.isdir(pth):
            for dirpath, dnames, fnames in os.walk(pth):
                for f in fnames:
                    m = re.search('^{}-(\d+).dat$'.format(k), f)
                    
                    if m is not None:
                        blockindex = int(m.group(1))

                        try:
                            self._loadblock(blockindex, dirpath, f, handlers)
                        except (IOError, ValueError) as e:
                            handlers['onerror']('Failed to load block #{} in path \'{}\'. It is recommended to delete the \'{}\' directory to do a complete resync. The error was: {}'.format(blockindex, pth, k, e))

            if len(self.blocks) == 0:
                handlers['onstatus']('No local blocks to load in path \'{}\'.'.format(pth))

                if k == 'tx':
                    handlers['onstatus']('Creating genesis block before starting peer sync...')
                    self._creategenesisblock(handlers)
            else:
                handlers['onstatus']('Done loading local blocks in path \'{}\'.'.format(pth))
        else:
            handlers['onstatus']('No local blocks to load.')

            handlers['onstatus']('Creating \'{}\' directory...'.format(pth))
            os.mkdir(pth)

            if k == 'tx':
                handlers['onstatus']('Creating genesis block before starting peer sync...')
                self._creategenesisblock(handlers)

        self.local_blocks_loaded = True

    def _creategenesisblock(self, handlers):
        GENESISTX.savelocal()

        # re-run
        self.loadlocal(handlers)

    def _loadblock(self, blockindex, dirpath, fname, handlers):
        # handlers['onstatus']('Loading block #{} ...'.format(blockindex))

        blkfile = open(os.path.join(dirpath, fname))
        blk = Block.deserialize_json(blkfile.read())

        if not blk.isgenesis():
            assert blk.parent == self.latestblock().blockid

        self.blocks.append(blk)

    def latestblock(self):
        assert len(self.blocks) != 0

        return self.blocks[-1]
    