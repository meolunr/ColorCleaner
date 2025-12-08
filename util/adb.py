import os
import subprocess
from os import PathLike

from ccglobal import MISC_DIR, log

_DATA_TMP_DIR = '/data/local/tmp'
_MODULE_DIR = '/data/adb/modules/colorcleaner'


def execute(command: str):
    return subprocess.run(['adb', 'shell', 'su', '-c', f'"{command}"']).returncode


def getoutput(command: str):
    popen = subprocess.Popen(['adb', 'shell', 'su', '-c', f'"{command}"'], stdout=subprocess.PIPE, universal_newlines=True)
    return popen.stdout


def push(src: str, dst: str):
    tmp_file = f'{_DATA_TMP_DIR}/{os.path.basename(src)}'
    subprocess.run(['adb', 'push', src, _DATA_TMP_DIR], stdout=subprocess.DEVNULL)
    # Use cp and rm commands to avoid moving file permissions simultaneously
    execute(f'cp -rf {tmp_file} {dst}')
    execute(f'rm -rf {tmp_file}')


def pull(src: str, dst: str | PathLike[str]):
    log(f'拉取设备文件: {src}')
    subprocess.run(['adb', 'pull', src, os.fspath(dst)], stdout=subprocess.DEVNULL)


def install_test_module():
    subprocess.run(['adb', 'push', f'{MISC_DIR}/module_template/CCTestModule.zip', '/sdcard'], stdout=subprocess.DEVNULL)
    execute('ksud module install /sdcard/CCTestModule.zip')
    execute('rm -f /sdcard/CCTestModule.zip')
    log(f'已安装 CC 测试模块，重启设备后生效')


def module_push(src_path: str, phone_path: str):
    log(f'CCTest 文件推送: {phone_path}')
    if phone_path.startswith('/system/'):
        overlay_dir_path = f'{_MODULE_DIR}{os.path.dirname(phone_path)}'
    else:
        overlay_dir_path = f'{_MODULE_DIR}{os.path.dirname(f'/system{phone_path}')}'
    execute(f'mkdir -p {overlay_dir_path}')
    push(src_path, overlay_dir_path)


def module_rm(phone_path: str):
    log(f'CCTest 文件删除: {phone_path}')
    if phone_path.startswith('/system/'):
        rm_path = phone_path
    else:
        rm_path = f'/system{phone_path}'

    if phone_path.startswith('/my_'):
        if is_dir(phone_path):
            execute(f'mkdir -p {_MODULE_DIR}{rm_path}')
            execute(f'touch {_MODULE_DIR}{rm_path}/.replace')
        else:
            execute(f'mkdir -p {_MODULE_DIR}{os.path.dirname(rm_path)}')
            execute(f'touch {_MODULE_DIR}{rm_path}')
    else:
        execute(f'mkdir -p {_MODULE_DIR}{os.path.dirname(rm_path)}')
        execute(f'mknod {_MODULE_DIR}{rm_path} c 0 0')


def module_overlay(phone_path: str):
    if phone_path.startswith('/system/'):
        module_push(f'system{phone_path}', phone_path)
    else:
        module_push(phone_path[1:], phone_path)


def exists(phone_path: str):
    return execute(f'test -e {phone_path}') == 0


def is_dir(phone_path: str):
    return execute(f'test -d {phone_path}') == 0


def get_apk_path(package: str):
    return getoutput(f'pm path {package}').read()[8:-1]
