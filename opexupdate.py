import json
import os
import re
import shutil
import subprocess
from enum import Enum
from glob import iglob
from pathlib import Path
from time import time

import requests

import ccglobal
import config
from util import adb
from util import crypto
from util import imgfile


class RegionCN(Enum):
    # @formatter:off
    FULL_OTA = ('https://component-ota-cn.allawntech.com/update/v6', 2, '\
                MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEApXYGXQpNL7gmMzzvajHa\
                oZIHQQvBc2cOEhJc7/tsaO4sT0unoQnwQKfNQCuv7qC1Nu32eCLuewe9LSYhDXr9\
                KSBWjOcCFXVXteLO9WCaAh5hwnUoP/5/Wz0jJwBA+yqs3AaGLA9wJ0+B2lB1vLE4\
                FZNE7exUfwUc03fJxHG9nCLKjIZlrnAAHjRCd8mpnADwfkCEIPIGhnwq7pdkbamZ\
                coZfZud1+fPsELviB9u447C6bKnTU4AaMcR9Y2/uI6TJUTcgyCp+ilgU0JxemrSI\
                PFk3jbCbzamQ6Shkw/jDRzYoXpBRg/2QDkbq+j3ljInu0RHDfOeXf3VBfHSnQ66H\
                CwIDAQAB',
                1615879139745,
                'params',
                'SCENE_1',
                'body',
                'opex > opexPackage')
    OPEX =     ('https://opex-service-cn.allawntech.com/queryUpdate', 1, '\
                MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAr/B2JwdaZIQqVpx10R4R\
                o/ZjCLzssu3vIZCKNwDh4LMBkeHRjcjtaVPoPvvTKY74XlMg7fmRv0iQELnlFNtH\
                jgg8YnmhZObUmpVdpHLhthRSBqpRKl2LhMgYtE/SELUKvzelw2byNcRnU9/PvbsA\
                Dcgz7IUFAzOvvtxnbaOd9CAthvO+0BTSk3dnBt6CT4nScgr13BAn6RTJI0wV5DZM\
                pLNsTEXiTcQT3ZX2LcT6bRN8yUmGuARjLh2VG7H1gSxjUUDsKcFmcJY/8zyB64nq\
                vX4Gya86c2bVaEd+CsMsOEYISWdVrG+Rf6y3BaG1DZRQDh0GD1cwtvA+JtvEmqGk\
                qwIDAQAB',
                1631001537253,
                None,
                'opex',
                None,
                'data')
    # @formatter:on

    def __init__(self, url: str, request_version: int, public_key: str, negotiation_version: int,
                 request_body_json_root: str, protected_key_json_root: str, response_body_json_root: str, opex_json_root: str):
        self.url = url
        self.request_version = str(request_version)
        self.public_key = public_key
        self.negotiation_version = str(negotiation_version)
        self.request_body_json_root = request_body_json_root
        self.protected_key_json_root = protected_key_json_root
        self.response_body_json_root = response_body_json_root
        self.opex_json_root = opex_json_root


def create_headers(prop_file: os.PathLike[str]):
    # @formatter:off
    headers: dict[str, str] = {
        'Content-Type' : 'application/json; charset=utf-8',
        'User-Agent'   : 'okhttp/5.3.2',
        'language'     : 'zh-CN',
        'infVersion'   : '1',
        'mode'         : 'client_auto',
        'nvCarrier'    : '10010111',
        'pipelineKey'  : 'ALLNET',
        'operator'     : 'ALLNET',
        'deviceId'     : '14BDCD6FD64180AF5E7791DF91B6AF8E9A3E7BC844997EB8C29252706DF97CA5',
        'queryMode'    : '0'
    }
    # @formatter:on

    with open(prop_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('ro.product.model='):
                headers['model'] = ccglobal.get_prop_value(line)
            elif line.startswith('ro.product.name='):
                headers['productName'] = ccglobal.get_prop_value(line)
            elif line.startswith('ro.build.version.release='):
                headers['androidVersion'] = f'Android{ccglobal.get_prop_value(line)}'
            elif line.startswith('ro.build.version.oplusrom='):
                coloros_version = f'ColorOS{re.match(r'V(\d+\.\d+\.\d+)', ccglobal.get_prop_value(line)).group(1)}'
                headers['osVersion'] = coloros_version
                headers['colorOSVersion'] = coloros_version
            elif line.startswith('ro.build.display.id='):
                headers['romVersion'] = ccglobal.get_prop_value(line)
            elif line.startswith('ro.build.version.ota='):
                headers['otaVersion'] = ccglobal.get_prop_value(line)
            elif line.startswith('ro.product.vendor.brand='):
                brand = ccglobal.get_prop_value(line)
                headers['brand'] = brand
                headers['brandSota'] = brand
            elif line.startswith('ro.oplus.image.my_stock.type='):
                headers['osType'] = ccglobal.get_prop_value(line)

    return headers


def create_request_body(headers: dict[str, str]):
    # @formatter:off
    request_body: dict[str, str] = {
        'mode'         : '0',
        'isRooted'     : '0',
        'isLocked'     : True,
        'type'         : '0',
        'deviceId'     : '14BDCD6FD64180AF5E7791DF91B6AF8E9A3E7BC844997EB8C29252706DF97CA5',
        'opex'         : {'check': True},
        'businessList' : [],
        'time'         : str(int(time() * 1000)),
        'otaVersion'   : headers['otaVersion']
    }
    # @formatter:on
    return request_body


def get_wrapped_json(keys: str, json_dict: dict):
    if not keys:
        return json_dict
    keys = keys.replace(' ', '')
    index = keys.find('>')

    if index == -1:
        return json_dict[keys]
    return get_wrapped_json(keys[index + 1:], json_dict[keys[:index]])


def get_opex_update_for_current(headers: dict[str, str], request_body: dict[str, str]):
    if config.OPEX_FULL_OTA_CHECK:
        operator = RegionCN.FULL_OTA
        headers['otaVersion'] = f'{headers['otaVersion'][:-17]}0001_000000000001'
    else:
        operator = RegionCN.OPEX

    key, iv, cipher = crypto.aes_encrypt(json.dumps(request_body).encode('utf-8'))
    request_body = {
        'cipher': cipher.decode('utf-8'),
        'iv': iv.decode('utf-8')
    }
    if operator.request_body_json_root:
        request_body = {
            operator.request_body_json_root: json.dumps(request_body)
        }

    protected_key = crypto.rsa_encrypt(operator.public_key, key)
    protected_key_dict = {
        operator.protected_key_json_root: {
            'protectedKey': protected_key.decode('utf-8'),
            'version': str(int(time() + 86400) * 1000),
            'negotiationVersion': operator.negotiation_version
        }
    }
    headers['version'] = operator.request_version
    headers['protectedKey'] = json.dumps(protected_key_dict)

    response = requests.post(operator.url, data=json.dumps(request_body), headers=headers, timeout=10)
    response_body = json.loads(response.content)
    if operator.response_body_json_root:
        response_body = json.loads(response_body[operator.response_body_json_root])

    iv = response_body['iv']
    cipher = response_body['cipher']
    response_body = json.loads(crypto.aes_decrypt(key, iv.encode('utf-8'), cipher.encode('utf-8')))

    return get_wrapped_json(operator.opex_json_root, response_body)


def unpack_img(opex_files: list[str]):
    if not os.path.isdir('opex'):
        os.mkdir('opex')

    ccglobal.patch_number = 0
    _7z = f'{ccglobal.LIB_DIR}/7za.exe'
    for file in opex_files:
        subprocess.run([_7z, 'e', file, 'opex.cfg', '-oopex'], check=True, stdout=subprocess.DEVNULL)
        with open('opex/opex.cfg', 'r', encoding='utf-8') as f:
            json_dict = json.load(f)
            business_code = json_dict['businessCode']
            ota_version_limits = json_dict['otaVersionLimits']
            ccglobal.patch_number += 1
            if not hasattr(ccglobal, 'device') and len(ota_version_limits) == 1:
                ccglobal.device = ota_version_limits.pop().split('_')[0]
        os.remove('opex/opex.cfg')

        subprocess.run([_7z, 'e', file, 'opex.img', '-oopex'], check=True, stdout=subprocess.DEVNULL)
        imgfile.unpack('opex/opex.img', business_code, 'opex')
        os.remove('opex/opex.img')


def is_cygwin_symlink(file: str):
    with open(file, 'rb') as f:
        if f.read(10) == b'!<symlink>':
            return True
    return False


def update_file(src: str, dst: str):
    ccglobal.log(f'更新系统文件: {dst}')
    if os.path.isfile(dst):
        os.remove(dst)
    elif os.path.isdir(dst):
        shutil.rmtree(dst)
    if is_cygwin_symlink(src):
        return

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    shutil.move(src, dst)


def run_on_rom(opex_files: list[str]):
    if not opex_files:
        return
    unpack_img(opex_files)

    for root, _, files in os.walk('opex'):
        for file in files:
            if file == 'opex.cfg':
                continue
            src = os.path.join(root, file)
            dst_splits = src[21:].replace('\\', '/').split('/')

            for item in ('my_product', 'my_stock', 'my_product/product_overlay'):
                dst = f'{item}/{'/'.join(dst_splits[1:])}'
                if os.path.exists(dst):
                    dst_splits[0] = item
                    break
            update_file(src, '/'.join(dst_splits))


def run_on_module(opex_files: list[str]):
    if not opex_files:
        return
    unpack_img(opex_files)

    for root, _, files in os.walk('opex'):
        for file in files:
            if file == 'opex.cfg':
                continue
            src = os.path.join(root, file)
            dst = src[21:].replace('\\', '/')
            update_file(src, dst)


def fetch_opex():
    prop_file = Path('my_manifest/build.prop')
    if not prop_file.is_file() and adb.is_connected():
        prop_file.parent.mkdir()
        adb.execute('cp /my_manifest/build.prop /data/local/tmp/')
        adb.pull('/data/local/tmp/build.prop', prop_file)
        adb.execute(f'rm -rf /data/local/tmp/build.prop')
    if not prop_file.is_file():
        return None

    headers = create_headers(prop_file)
    request_body = create_request_body(headers)
    return get_opex_update_for_current(headers, request_body)
