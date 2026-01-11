import sys
from datetime import datetime

LIB_DIR = f'{sys.path[0]}/lib'
MISC_DIR = f'{sys.path[0]}/misc'
PARTITION_FILESYSTEM_JSON = 'config/partition_filesystem.json'
UPDATED_APP_JSON = 'product/UpdatedApp.json'

device: str
version: str
sdk: int
kmi: str
patch_number: int


def log(string: str):
    now = datetime.now().strftime('[%m-%d %H:%M:%S]')
    print(f'{now} {string}')


def get_prop_value(prop: str):
    return prop.rstrip().split('=')[1]


def patch_number_suffix():
    global patch_number
    if patch_number > 0:
        return f'-P{patch_number:02d}'
    else:
        return ''
