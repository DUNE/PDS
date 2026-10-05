import json
import os
import time


class Journal:
    """Append and fsync transitions; never overwrite an existing scan."""
    def __init__(self, path):
        self.file = open(path, 'x')
        self.sequence = 0

    def record(self, event, **data):
        self.sequence += 1
        self.file.write(json.dumps(dict(sequence=self.sequence, unix_ns=time.time_ns(), event=event, **data)) + '\n')
        self.file.flush()
        os.fsync(self.file.fileno())

    def close(self):
        self.file.close()
