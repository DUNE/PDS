#!/usr/bin/env python3
"""Verify this recovery snapshot without writing files or contacting hardware."""
import hashlib
import json
from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'snapshot-manifest.json').read_text())
for relative, expected in manifest['files'].items():
    path = root / relative
    if not path.is_file():
        raise SystemExit('Missing: ' + relative)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit('SHA-256 mismatch: ' + relative)
board = json.loads((root / 'board/board-files.json').read_text())
count = 0
with tarfile.open(root / 'board/board-rootfs.tar.gz') as archive:
    for member in archive:
        if member.name.startswith('/') or '..' in Path(member.name).parts:
            raise SystemExit('Unexpected archive member: ' + member.name)
        if member.isfile():
            expected = board['/' + member.name]['sha256']
            actual = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
            if actual != expected:
                raise SystemExit('Board payload mismatch: ' + member.name)
            count += 1
print('Verified {} snapshot files and {} board payload files; no hardware contacted.'.format(
    len(manifest['files']), count))
