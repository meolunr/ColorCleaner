import io
import json
import os
import re
import shutil
import subprocess
from enum import Enum, auto
from glob import iglob
from pathlib import Path
from zipfile import ZipFile

import ccglobal
import config
from build.apkfile import ApkFile
from util import adb, template, myoverlay


class NewApp(object):
    class Source(Enum):
        DATA = auto()
        ROM = auto()
        MODULE = auto()

    def __init__(self, package, new_apks, old_dir):
        self.package = package
        self.new_apks = new_apks
        self.rom_old_dir = myoverlay.local_real_path(old_dir)
        self.module_old_dir = old_dir[1:]
        self.source = None
        self.version_code = None


def get_updated_system_packages():
    data = set()
    for line in adb.getoutput('pm list packages -f -s'):
        line = line[8:].strip()
        if not line.startswith('/data/app/'):
            continue
        data.add(line.rsplit('=', 1)[1])
    return data


def get_hidden_system_package_paths():
    paths = {}
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
                paths[package] = match.group(1)

    return paths


def read_record():
    ccglobal.log('读取系统应用更新记录')
    json_path = Path(ccglobal.UPDATED_APP_JSON)
    if not json_path.is_file():
        json_path.parent.mkdir(exist_ok=True)
        adb.pull(f'/{ccglobal.UPDATED_APP_JSON}', json_path)
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
    ccglobal.log('写入系统应用更新记录')
    with open(ccglobal.UPDATED_APP_JSON, 'w+', encoding='utf-8', newline='') as f:
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


def load_version_code(apps: dict):
    pattern = re.compile(r'package:(.+) versionCode:(\d+)')
    for line in adb.getoutput('pm list packages -s --show-versioncode'):
        match = re.search(pattern, line)
        if not match:
            continue
        app = apps.get(match.group(1))
        if app:
            app.version_code = int(match.group(2))


def fetch_updated_apps():
    apps: dict[str, NewApp] = {}

    data = get_updated_system_packages()
    system_package_paths = get_hidden_system_package_paths()
    for package in data:
        new_apks = adb.get_apk_path(package)
        app = NewApp(package, new_apks, system_package_paths[package])
        app.source = NewApp.Source.DATA
        apps[package] = app

    rom, module = read_record()
    for package in rom:
        if package in apps:
            continue
        new_apks = adb.get_apk_path(package)
        app = NewApp(package, new_apks, os.path.dirname(new_apks[0]))
        app.source = NewApp.Source.ROM
        apps[package] = app
    for package in module:
        if package in apps:
            continue
        new_apks = adb.get_apk_path(package)
        app = NewApp(package, new_apks, os.path.dirname(new_apks[0]))
        app.source = NewApp.Source.MODULE
        apps[package] = app

    load_version_code(apps)
    return set(apps.values())


def pull_apks_from_device(new_apks: list[str], old_dir: str):
    base_apk = f'{old_dir}/{os.path.basename(old_dir)}.apk'
    new_apk = new_apks.pop(0)
    adb.pull(new_apk, base_apk)
    extract_lib = ApkFile(base_apk).extract_native_libs()

    # Pull split apks
    for new_apk in new_apks:
        old_apk = f'{old_dir}/{os.path.basename(new_apk)}'
        adb.pull(new_apk, old_apk)

    if extract_lib is None and len(new_apks) == 0:
        with ZipFile(base_apk) as f:
            dirs = {x.split('/')[1] for x in f.namelist() if x.startswith('lib/')}
            extract_lib = len(dirs) > 1

    if extract_lib:
        _7z = f'{ccglobal.LIB_DIR}/7za.exe'
        for new_apk in iglob(f'{old_dir}/*.apk'):
            subprocess.run([_7z, 'e', '-aoa', new_apk, 'lib/arm64-v8a', f'-o{old_dir}/lib/arm64'], stdout=subprocess.DEVNULL)


def run_on_rom():
    if not adb.is_connected():
        return
    packages = set()
    for app in fetch_updated_apps():
        if app.version_code <= ApkFile(f'{app.rom_old_dir}/{os.path.basename(app.rom_old_dir)}.apk').version_code():
            # Oplus has updated the apk in ROM
            continue
        ccglobal.log(f'更新系统应用: {app.rom_old_dir}')
        shutil.rmtree(app.rom_old_dir)
        os.mkdir(app.rom_old_dir)
        pull_apks_from_device(app.new_apks, app.rom_old_dir)
        packages.add(app.package)

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
    if not adb.is_connected():
        return
    packages = set()
    apps = {x for x in fetch_updated_apps() if x.source != NewApp.Source.ROM and x.package in config.MODIFY_PACKAGE}
    remove_oat_output = io.StringIO()
    remove_data_app_output = io.StringIO()

    for app in apps:
        ccglobal.log(f'更新系统应用: {app.module_old_dir}')
        os.makedirs(app.module_old_dir)
        pull_apks_from_device(app.new_apks, app.module_old_dir)
        packages.add(app.package)
        remove_oat_output.write(f'/{app.module_old_dir}/oat\n')
        remove_data_app_output.write(f'removeDataApp {app.package}\n')

    write_record(module=packages)
    template.substitute(f'{ccglobal.MISC_DIR}/module_template/Patch/customize.sh',
                        var_remove_oat=remove_oat_output.getvalue(), var_remove_data_app=remove_data_app_output.getvalue())
