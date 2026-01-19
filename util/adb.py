import os
import subprocess

import ccglobal
import config

_DATA_TMP_DIR = '/data/local/tmp'
_MODULE_DIR = '/data/adb/modules/colorcleaner'
_OVERLAYFS_MODULE_DIR = '/data/adb/metamodule/mnt/colorcleaner'


def is_connected():
    lines = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE).stdout.decode().strip().splitlines()
    num = len(lines)
    if num == 2:
        return True
    elif num < 2:
        ccglobal.log('未检测到 adb 设备连接')
        return False
    else:
        ccglobal.log('检测到多个 adb 设备连接')
        return False


def execute(command: str):
    return subprocess.run(['adb', 'shell', 'su', '-c', f'"{command}"']).returncode


def getoutput(command: str):
    popen = subprocess.Popen(['adb', 'shell', 'su', '-c', f'"{command}"'], stdout=subprocess.PIPE, universal_newlines=True)
    return popen.stdout


def push(src: str, dst: str):
    if dst.startswith('/sdcard'):
        subprocess.run(['adb', 'push', src, dst], stdout=subprocess.DEVNULL)
    else:
        subprocess.run(['adb', 'push', src, _DATA_TMP_DIR], stdout=subprocess.DEVNULL)
        tmp_file = f'{_DATA_TMP_DIR}/{os.path.basename(src)}'
        # Use cp and rm commands to avoid moving file permissions simultaneously
        execute(f'cp -rf {tmp_file} {dst}')
        execute(f'rm -rf {tmp_file}')


def pull(src: str, dst: str | os.PathLike[str]):
    ccglobal.log(f'拉取设备文件: {src}')
    subprocess.run(['adb', 'pull', src, os.fspath(dst)], stdout=subprocess.DEVNULL)


def install_test_module():
    if config.TEST_MODULE_OVERLAYFS:
        push(f'{ccglobal.MISC_DIR}/module_template/CCTestModule-OverlayFS.zip', '/sdcard/CCTestModule.zip')
        execute('ksud module install /sdcard/CCTestModule.zip')
        execute('rm /sdcard/CCTestModule.zip')

        for partition in config.UNPACK_PARTITIONS:
            if partition in ('boot', 'system'):
                continue
            partition_dir = f'{_OVERLAYFS_MODULE_DIR}/{partition}'
            execute(f'mkdir {partition_dir}')
            execute(f'busybox chcon --reference=/{partition} {partition_dir}')
        ccglobal.log(f'已安装 CC 测试模块')
    else:
        push(f'{ccglobal.MISC_DIR}/module_template/CCTestModule-MagicMount.zip', '/sdcard/CCTestModule.zip')
        execute('ksud module install /sdcard/CCTestModule.zip')
        execute('rm /sdcard/CCTestModule.zip')
        ccglobal.log(f'已安装 CC 测试模块，重启设备后生效')


def module_push(src_path: str, device_path: str):
    ccglobal.log(f'CCTest 文件推送: {device_path}')
    if config.TEST_MODULE_OVERLAYFS:
        overlay_dir_path = f'{_OVERLAYFS_MODULE_DIR}{os.path.dirname(device_path)}'
    else:
        if device_path.startswith('/system/'):
            overlay_dir_path = f'{_MODULE_DIR}{os.path.dirname(device_path)}'
        else:
            overlay_dir_path = f'{_MODULE_DIR}{os.path.dirname(f'/system{device_path}')}'
    execute(f'mkdir -p {overlay_dir_path}')
    push(src_path, overlay_dir_path)


def module_rm(device_path: str):
    ccglobal.log(f'CCTest 文件删除: {device_path}')
    if config.TEST_MODULE_OVERLAYFS:
        rm_path_parent = f'{_OVERLAYFS_MODULE_DIR}{os.path.dirname(device_path)}'
    else:
        if device_path.startswith('/system/'):
            rm_path_parent = f'{_MODULE_DIR}{os.path.dirname(device_path)}'
        else:
            rm_path_parent = f'{_MODULE_DIR}/system{os.path.dirname(device_path)}'

    if device_path.startswith('/my_'):
        rm_path = f'{rm_path_parent}/{os.path.basename(device_path)}'
        if is_dir(device_path):
            execute(f'mkdir -p {rm_path}')
            execute(f'touch {rm_path}/.replace')
        else:
            execute(f'mkdir -p {rm_path_parent}')
            execute(f'touch {rm_path}')
    else:
        execute(f'mkdir -p {rm_path_parent}')
        execute(f'mknod {_OVERLAYFS_MODULE_DIR}{device_path} c 0 0')


def module_overlay(device_path: str):
    if device_path.startswith('/system/'):
        module_push(f'system{device_path}', device_path)
    else:
        module_push(device_path[1:], device_path)


def is_dir(device_path: str):
    return execute(f'test -d {device_path}') == 0


def get_apk_path(package: str):
    path = []
    for line in getoutput(f'pm path {package}'):
        path.append(line[8:-1])
    return path
