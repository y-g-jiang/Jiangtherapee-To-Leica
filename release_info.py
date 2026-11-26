import json
import re

VERSION='1.0.5'
PRODUCT='Jiangtherapee to Leica'
REPOSITORY='https://github.com/y-g-jiang/Jiangtherapee-To-Leica'
SIGNAL_URL=REPOSITORY+'/releases/latest/download/jtl-update.json'
SUPPORT_URL='https://github.com/y-g-jiang/Support_Me_QR_Code'
LIMIT=65536

def version_tuple(value):
    if not isinstance(value,str) or not re.fullmatch(r'(?:0|[1-9][0-9]{0,8})(?:\.(?:0|[1-9][0-9]{0,8})){2}',value):raise ValueError('version')
    return tuple(map(int,value.split('.')))

def windows_asset(version):
    version_tuple(version)
    return f'Jiangtherapee-to-Leica-{version}-Windows-x64.exe'

def read_signal(data):
    if len(data)>LIMIT:raise ValueError('size')
    feed=json.loads(data.decode('utf-8'))
    if not isinstance(feed,dict) or type(feed.get('schema')) is not int or feed['schema']!=1 or feed.get('product')!='JTL' or feed.get('channel')!='stable':raise ValueError('channel')
    release=feed['release']
    if release is None:return None
    if not isinstance(release,dict):raise ValueError('release')
    version=release['version'];version_tuple(version);package=release['package']
    if not isinstance(package,dict) or package.get('url')!=f'{REPOSITORY}/releases/download/v{version}/{windows_asset(version)}':raise ValueError('origin')
    if type(package.get('size')) is not int or not 0<package['size']<=2**53-1 or not isinstance(package.get('sha256'),str) or not re.fullmatch('[0-9a-fA-F]{64}',package['sha256']):raise ValueError('package')
    return version
