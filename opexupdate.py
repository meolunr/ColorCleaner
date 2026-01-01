from enum import Enum
from time import time

import config


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


# @formatter:off
headers = {
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
request_body = {
    'mode'         : '0',
    'time'         : str(int(time() * 1000)),
    'isRooted'     : '0',
    'isLocked'     : True,
    'type'         : '0',
    'deviceId'     : '14BDCD6FD64180AF5E7791DF91B6AF8E9A3E7BC844997EB8C29252706DF97CA5',
    'opex'         : {'check': True},
    'businessList' : []
}
# @formatter:on

def create_header():
    pass


def check_opex_update():
    if config.OPEX_FULL_OTA_CHECK:
        operator = RegionCN.FULL_OTA
    else:
        operator = RegionCN.OPEX


def run_on_rom():
    pass


def run_on_module():
    pass
