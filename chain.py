import time
import os
import thread
import re
import sqlite3

from block import *

conn = sqlite3.connect('blocks.db')
c = conn.cursor()

class Chain:
    def __init__(self):
        self.blocks = []

    def loadlocal(self, handlers):
        thread.start_new_thread(self._loadlocalloop, (handlers,))

    def _loadlocalloop(self, handlers):
        time.sleep(5)
        handlers['onstatus']('Loading local blocks...')

        if os.path.isdir('./blocks'):
            for dirpath, dnames, fnames in os.walk("./blocks"):
                for f in fnames:
                    m = re.search('^block-(\d+).dat$', f)
                    
                    if m is not None:
                        blockindex = int(m.group(1))

                        try:
                            self._loadblock(blockindex, dirpath, f, handlers)
                        except (IOError, ValueError) as e:
                            handlers['onerror']('Failed to load block #{}. It is recommended to delete the \'blocks\' directory to do a complete resync. The error was: {}'.format(blockindex, e))

            if len(self.blocks) == 0:
                handlers['onstatus']('No local blocks to load.')

                handlers['onstatus']('Creating genesis block before starting peer sync...')
                self._creategenesisblock(handlers)
            else:
                handlers['onstatus']('Done loading local blocks. Now, starting peer sync.')
                handlers['oncomplete']()
        else:
            handlers['onstatus']('No local blocks to load.')

            handlers['onstatus']('Creating \'blocks\' directory...')
            os.mkdir('./blocks')

            handlers['onstatus']('Creating genesis block before starting peer sync...')
            self._creategenesisblock(handlers)

    def _creategenesisblock(self, handlers):
        gen = open('./blocks/block-{}.dat'.format(GENESISBLOCK.blockid), 'w+')
        gen.write(GENESISBLOCK.serialize_json())
        gen.close()

        # re-run
        self.loadlocal(handlers)

    def _loadblock(self, blockindex, dirpath, fname, handlers):
        handlers['onstatus']('Loading block #{} ...'.format(blockindex))

        blkfile = open(os.path.join(dirpath, fname))
        blk = Block.deserialize_json(blkfile.read())

        if not blk.isgenesis():
            assert blk.parent == self.latestblock().blockid

        self.blocks.append(blk)

    def latestblock(self):
        assert len(self.blocks) != 0

        return self.blocks[-1]
    