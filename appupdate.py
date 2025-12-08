import io
import json
import os
import re
import shutil
import subprocess
from enum import Enum, auto
from zipfile import ZipFile

import config
from build.apkfile import ApkFile
from ccglobal import LIB_DIR, MISC_DIR, UPDATED_APP_JSON, log
from util import adb, template


class NewApp(object):
    class Source(Enum):
        ROM = auto()
        MODULE = auto()
        DATA = auto()

    def __init__(self, package, data_path, system_path):
        self.package = package
        self.data_path = data_path
        self.system_path = system_path
        self.system_path_rom = self._combine_system_path(system_path, False)
        self.system_path_module = self._combine_system_path(system_path, True)
        self.system_path_rom_with_apk = f'{self.system_path_rom}/{os.path.basename(self.system_path_rom)}.apk'
        self.source = None
        self.version_code = None

    @staticmethod
    def _combine_system_path(system_path, is_module):
        if (is_module and not system_path.startswith('/system/')) or (not is_module and system_path.startswith('/system/')):
            system_path = f'/system{system_path}'
        return system_path[1:]


def check_adb_device() -> bool:
    lines = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE).stdout.decode().strip().splitlines()
    num = len(lines)
    if num == 2:
        return False
    elif num < 2:
        log('未检测到 adb 设备连接，不再进行系统应用更新')
        return True
    else:
        log('检测到多个 adb 设备连接，不再进行系统应用更新')
        return True


def get_app_in_data():
    path_map = {}

    for line in adb.getoutput('pm list packages -f -s'):
        line = line[8:].strip()
        if not line.startswith('/data/app/'):
            continue
        splits = line.rsplit('=', 1)
        path_map[splits[1]] = splits[0]

    return path_map


def get_app_in_system():
    path_map = {}
    pattern_package = re.compile(r' {2}Package \[(.+)]')
    pattern_path = re.compile(r' {4}codePath=(.+)')

    section = False
    package = ''
    for line in adb.getoutput('dumpsys package packages'):
        if line.startswith('Hidden system packages:'):
            section = True
        elif section:
            match = re.search(pattern_package, line)
            if match:
                package = match.group(1)
            match = re.search(pattern_path, line)
            if match:
                path_map[package] = match.group(1)

    return path_map


def read_record():
    log('读取系统应用更新记录')
    if not os.path.isfile(UPDATED_APP_JSON):
        if not os.path.isdir('product'):
            os.mkdir('product')
        adb.pull(f'/{UPDATED_APP_JSON}', 'product')
        open(UPDATED_APP_JSON, 'a').close()

    with open(UPDATED_APP_JSON, 'r', encoding='utf-8') as f:
        try:
            data: dict = json.load(f)
            rom, module = set(data.get('rom', set())), set(data.get('module', set()))
        except json.decoder.JSONDecodeError:
            rom, module = set(), set()
    return rom, module


def write_record(*, rom: set = None, module: set = None):
    rom_to_be_written, module_to_be_written = read_record()
    log('写入系统应用更新记录')
    with open(UPDATED_APP_JSON, 'w+', encoding='utf-8', newline='\n') as f:
        if rom is not None:
            rom_to_be_written = rom
        if module is not None:
            module_to_be_written = module

        # Move rom-record of the app that has been updated when building rom to module-record
        for package in module_to_be_written:
            if package in rom_to_be_written:
                rom_to_be_written.remove(package)

        data = {}
        if len(rom_to_be_written) != 0:
            data['rom'] = tuple(rom_to_be_written)
        if len(module_to_be_written) != 0:
            data['module'] = tuple(module_to_be_written)
        json.dump(data, f, indent=4)


def load_version_code(app_map: dict):
    pattern = re.compile(r'package:(.+) versionCode:(\d+)')
    for line in adb.getoutput('pm list packages -s --show-versioncode'):
        match = re.search(pattern, line)
        if not match:
            continue
        app = app_map.get(match.group(1))
        if app:
            app.version_code = int(match.group(2))


def fetch_updated_app():
    app_map: dict[str, NewApp] = {}

    path_map_data = get_app_in_data()
    path_map_system = get_app_in_system()
    for package, path_in_data in path_map_data.items():
        # Skip xiaomi service framework
        if package == 'com.xiaomi.xmsf':
            continue
        app = NewApp(package, path_in_data, path_map_system[package])
        app.source = NewApp.Source.DATA
        app_map[package] = app

    rom, module = read_record()
    for package in rom:
        if package in app_map:
            continue
        path = adb.get_apk_path(package)
        app = NewApp(package, path, os.path.dirname(path))
        app.source = NewApp.Source.ROM
        app_map[package] = app
    for package in module:
        if package in app_map:
            continue
        path = adb.get_apk_path(package)
        app = NewApp(package, path, os.path.dirname(path))
        app.source = NewApp.Source.MODULE
        app_map[package] = app

    load_version_code(app_map)
    return set(app_map.values())


def pull_apk_from_phone(app: NewApp):
    adb.pull(app.data_path, app.system_path_rom_with_apk)

    extract_lib = ApkFile(app.system_path_rom_with_apk).extract_native_libs()
    if extract_lib is None:
        with ZipFile(app.system_path_rom_with_apk) as f:
            dirs = {x.split('/')[1] for x in f.namelist() if x.startswith('lib/')}
            extract_lib = len(dirs) > 1

    if extract_lib:
        _7z = f'{LIB_DIR}/7za.exe'
        subprocess.run([_7z, 'e', '-aoa', app.system_path_rom_with_apk, 'lib/arm64-v8a', f'-o{app.system_path_rom}/lib/arm64'], stdout=subprocess.DEVNULL)


def run_on_rom():
    if check_adb_device():
        return
    apps = fetch_updated_app()
    packages = set()
    for app in apps:
        if app.version_code <= ApkFile(app.system_path_rom_with_apk).version_code():
            # Xiaomi has updated the apk in ROM
            continue
        log(f'更新系统应用: {app.system_path_rom}')
        pull_apk_from_phone(app)
        packages.add(app.package)

        oat = f'{app.system_path_rom}/oat'
        if os.path.exists(oat):
            shutil.rmtree(oat)

    write_record(rom=packages, module=set())
    with open('vendor/build.prop', 'r+', encoding='utf-8', newline='') as f:
        lines = []
        for line in f.readlines():
            if not line.startswith('ro.control_privapp_permissions=enforce'):
                lines.append(line)
        f.seek(0)
        f.truncate()
        f.writelines(lines)


def run_on_module():
    if check_adb_device():
        return
    apps = {x for x in fetch_updated_app() if x.source != NewApp.Source.ROM and x.package in config.MODIFY_PACKAGE}
    packages = set()
    remove_oat_output = io.StringIO()
    remove_data_app_output = io.StringIO()
    package_cache_output = io.StringIO()
    mount_output = io.StringIO()

    for app in apps:
        log(f'更新系统应用: {app.system_path_module}')
        os.makedirs(app.system_path_rom)
        pull_apk_from_phone(app)
        packages.add(app.package)
        remove_oat_output.write(f'/{app.system_path_module}/oat\n')
        remove_data_app_output.write(f'removeDataApp {app.package}\n')
        package_cache_output.write(f'rm -f /data/system/package_cache/*/{os.path.basename(app.system_path)}-*\n')
        mount_output.write(f'mount -o bind $MODDIR/{app.system_path_module} {app.system_path}\n')

    write_record(module=packages)
    template.substitute(f'{MISC_DIR}/module_template/AppUpdate/customize.sh',
                        var_remove_oat=remove_oat_output.getvalue(), var_remove_data_app=remove_data_app_output.getvalue())
    template.substitute(f'{MISC_DIR}/module_template/AppUpdate/post-fs-data.sh', var_package_cache=package_cache_output.getvalue())
    template.substitute(f'{MISC_DIR}/module_template/AppUpdate/post-fs-data.sh.bak', var_mount=mount_output.getvalue())
