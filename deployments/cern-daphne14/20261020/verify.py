#!/usr/bin/env python3
import pathlib,json,hashlib
r=pathlib.Path(__file__).resolve().parent
m=json.loads((r/'manifest.json').read_text())
for name,want in m['files'].items():
 p=r/name
 assert p.is_file(),name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==want,name
print('Verified',len(m['files']),'files')
