import json
import re
from enum import Enum
from time import time

import requests

import ccglobal
import config
from util import crypto


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


def create_headers(prop_file: str):
    # @formatter:off
    headers: dict[str, str] = {
        'Content-Type' : 'application/json; charset=utf-8',
        'User-Agent'   : 'Thunder',
        'language'     : 'zh-CN',
        'infVersion'   : '1',
        'mode'         : 'client_auto',
        'nvCarrier'    : '10010111',
        'pipelineKey'  : 'ALLNET',
        'operator'     : 'ALLNET',
        'brand'        : 'OnePlus',
        'brandSota'    : 'OnePlus',
        'osType'       : 'domestic_OnePlus',
        'deviceId'     : '14BDCD6FD64180AF5E7791DF91B6AF8E9A3E7BC844997EB8C29252706DF97CA5',
        'queryMode'    : '0'
    }
    # @formatter:on

    with open(prop_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('ro.product.model='):
                headers['model'] = ccglobal.getvalue(line)
            elif line.startswith('ro.product.name='):
                headers['productName'] = ccglobal.getvalue(line)
            elif line.startswith('ro.build.version.release='):
                headers['androidVersion'] = f'Android{ccglobal.getvalue(line)}'
            elif line.startswith('ro.build.version.oplusrom='):
                coloros_version = f'ColorOS{re.match(r'V(\d+\.\d+\.\d+)', ccglobal.getvalue(line)).group(1)}'
                headers['osVersion'] = coloros_version
                headers['colorOSVersion'] = coloros_version
            elif line.startswith('ro.build.display.id='):
                headers['romVersion'] = ccglobal.getvalue(line)
            elif line.startswith('ro.build.version.ota='):
                headers['otaVersion'] = ccglobal.getvalue(line)

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


def fetch_opex_update(headers: dict[str, str], request_body: dict[str, str]):
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

    response = requests.post(operator.url, data=json.dumps(request_body), headers=headers)
    response_body = json.loads(response.content)
    if operator.response_body_json_root:
        response_body = json.loads(response_body[operator.response_body_json_root])

    iv = response_body['iv']
    cipher = response_body['cipher']
    response_body = json.loads(crypto.aes_decrypt(key, iv.encode('utf-8'), cipher.encode('utf-8')))

    return get_wrapped_json(operator.opex_json_root, response_body)


def run_on_rom():
    headers = create_headers('build.prop')
    request_body = create_request_body(headers)
    opex_list = fetch_opex_update(headers, request_body)
    print(opex_list)


def run_on_module():
    pass
