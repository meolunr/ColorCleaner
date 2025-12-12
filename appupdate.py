import io
import json
import os
import re
import shutil
import subprocess
from enum import Enum, auto
from pathlib import Path
from zipfile import ZipFile

import config
from build.apkfile import ApkFile
from ccglobal import LIB_DIR, MISC_DIR, UPDATED_APP_JSON, log
from util import adb, template


class NewApp(object):
    class Source(Enum):
        DATA = auto()
        ROM = auto()
        MODULE = auto()

    def __init__(self, package, new_apk, old_dir):
        self.package = package
        self.new_apk = new_apk
        self.rom_old_dir = self._combine_rom_path(old_dir)
        self.module_old_dir = self._combine_module_path(old_dir)
        self.source = None
        self.version_code = None

    @staticmethod
    def _combine_rom_path(old_dir):
        path = NewApp._get_real_old_dir(old_dir)
        if path.startswith('/system/'):
            return f'system{path}'
        else:
            return path[1:]

    @staticmethod
    def _combine_module_path(old_dir):
        return old_dir[1:]

    @staticmethod
    def _get_real_old_dir(old_dir):
        if not old_dir.startswith('/product/'):
            return old_dir

        my_partitions = {x for x in config.unpack_partitions if x.startswith('my_')}
        for my_partition in my_partitions:
            my_path = f'/{my_partition}{old_dir[8:]}'
            if adb.exists(my_path):
                return my_path

        return old_dir


def is_adb_connected() -> bool:
    lines = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE).stdout.decode().strip().splitlines()
    num = len(lines)
    if num == 2:
        return True
    elif num < 2:
        log('未检测到 adb 设备连接，不再进行系统应用更新')
        return False
    else:
        log('检测到多个 adb 设备连接，不再进行系统应用更新')
        return False


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
    json_path = Path(UPDATED_APP_JSON)
    if not json_path.is_file():
        json_path.parent.mkdir(exist_ok=True)
        adb.pull(f'/{UPDATED_APP_JSON}', json_path)
        open(json_path, 'a').close()

    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data: dict = json.load(f)
            rom, module = set(data.get('rom', set())), set(data.get('module', set()))
        except json.decoder.JSONDecodeError:
            rom, module = set(), set()
    return rom, module


def write_record(*, rom: set = None, module: set = None):
    rom_to_be_written, module_to_be_written = read_record()
    log('写入系统应用更新记录')
    with open(UPDATED_APP_JSON, 'w+', encoding='utf-8', newline='') as f:
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
    for package, new_apk in path_map_data.items():
        # Skip heytap mobile service
        if package == 'com.heytap.htms':
            continue
        app = NewApp(package, new_apk, path_map_system[package])
        app.source = NewApp.Source.DATA
        app_map[package] = app

    rom, module = read_record()
    for package in rom:
        if package in app_map:
            continue
        new_apk = adb.get_apk_path(package)
        app = NewApp(package, new_apk, os.path.dirname(new_apk))
        app.source = NewApp.Source.ROM
        app_map[package] = app
    for package in module:
        if package in app_map:
            continue
        new_apk = adb.get_apk_path(package)
        app = NewApp(package, new_apk, os.path.dirname(new_apk))
        app.source = NewApp.Source.MODULE
        app_map[package] = app

    load_version_code(app_map)
    return set(app_map.values())


def pull_apk_from_phone(new_apk: str, old_apk: str):
    adb.pull(new_apk, old_apk)

    extract_lib = ApkFile(old_apk).extract_native_libs()
    if extract_lib is None:
        with ZipFile(old_apk) as f:
            dirs = {x.split('/')[1] for x in f.namelist() if x.startswith('lib/')}
            extract_lib = len(dirs) > 1

    if extract_lib:
        _7z = f'{LIB_DIR}/7za.exe'
        subprocess.run([_7z, 'e', '-aoa', old_apk, 'lib/arm64-v8a', f'-o{os.path.dirname(old_apk)}/lib/arm64'], stdout=subprocess.DEVNULL)


def run_on_rom():
    if not is_adb_connected():
        return
    apps = fetch_updated_app()
    packages = set()
    for app in apps:
        old_apk = f'{app.rom_old_dir}/{os.path.basename(app.rom_old_dir)}.apk'
        if app.version_code <= ApkFile(old_apk).version_code():
            # Oplus has updated the apk in ROM
            continue
        log(f'更新系统应用: {app.rom_old_dir}')
        pull_apk_from_phone(app.new_apk, old_apk)
        packages.add(app.package)

        oat = f'{app.rom_old_dir}/oat'
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
    if not is_adb_connected():
        return
    apps = {x for x in fetch_updated_app() if x.source != NewApp.Source.ROM and x.package in config.MODIFY_PACKAGE}
    packages = set()
    remove_oat_output = io.StringIO()
    remove_data_app_output = io.StringIO()
    package_cache_output = io.StringIO()

    for app in apps:
        log(f'更新系统应用: {app.module_old_dir}')
        os.makedirs(app.module_old_dir)
        apk_name = os.path.basename(app.module_old_dir)
        pull_apk_from_phone(app.new_apk, f'{app.module_old_dir}/{apk_name}.apk')
        packages.add(app.package)
        remove_oat_output.write(f'/{app.module_old_dir}/oat\n')
        remove_data_app_output.write(f'removeDataApp {app.package}\n')
        package_cache_output.write(f'rm -f /data/system/package_cache/*/{apk_name}-*\n')

    write_record(module=packages)
    template.substitute(f'{MISC_DIR}/module_template/Patch/customize.sh',
                        var_remove_oat=remove_oat_output.getvalue(), var_remove_data_app=remove_data_app_output.getvalue())
    template.substitute(f'{MISC_DIR}/module_template/Patch/post-fs-data.sh', var_package_cache=package_cache_output.getvalue())
