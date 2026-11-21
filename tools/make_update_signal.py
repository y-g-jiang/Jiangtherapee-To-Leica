import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from release_info import REPOSITORY,VERSION,read_signal,windows_asset


def build(directory):
    binary=directory/windows_asset(VERSION);digest=hashlib.sha256()
    with binary.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    package={'url':f'{REPOSITORY}/releases/download/v{VERSION}/{binary.name}','size':binary.stat().st_size,'sha256':digest.hexdigest()}
    raw=(json.dumps({'schema':1,'product':'JTL','channel':'stable','release':{'version':VERSION,'package':package}},indent=2)+'\n').encode('utf-8')
    if read_signal(raw)!=VERSION:raise ValueError('Invalid JTL signal')
    (directory/'jtl-update.json').write_bytes(raw)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);build(parser.parse_args().directory)
