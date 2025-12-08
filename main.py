import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from glob import glob
from pathlib import Path

import appupdate
import config
import customize
import vbmeta
from ccglobal import LIB_DIR, MISC_DIR, UPDATED_APP_JSON, log
from util import imgfile, template


def dump_payload(file: str):
    log(f'解压 Payload: {file}')
    payload_extract = f'{LIB_DIR}/payload_extract.exe'
    subprocess.run([payload_extract, '-x', '-i', file, '-o', 'images'], check=True)


def remove_official_recovery():
    log('去除官方 Recovery')
    recovery = Path('images/recovery.img')
    recovery.unlink(True)


def unpack_img():
    extract_erofs = f'{LIB_DIR}/extract.erofs.exe'
    magiskboot = f'{LIB_DIR}/magiskboot.exe'
    partition_filesystem = {}

    for partition in config.unpack_partitions:
        img = f'{partition}.img'
        file = f'images/{img}'
        filesystem = imgfile.filesystem(file)
        log(f'提取分区文件: {img}, 格式: {filesystem}')
        match filesystem:
            case imgfile.FileSystem.EROFS:
                subprocess.run([extract_erofs, '-x', '-i', file], check=True)
            case imgfile.FileSystem.BOOT:
                os.mkdir(partition)
                shutil.copy(file, f'{partition}/{img}')
                os.chdir(partition)
                subprocess.run([magiskboot, 'unpack', img], check=True)
                os.chdir('..')
        partition_filesystem[partition] = filesystem.name

    if not os.path.isdir('config'):
        os.mkdir('config')
    with open('config/partition_filesystem.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(partition_filesystem, f, indent=4)


def read_rom_information():
    def getvalue(prop: str):
        return prop.rstrip().split('=')[1]

    with open('my_manifest/build.prop', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('ro.product.name'):
                config.device = getvalue(line)
            elif line.startswith('ro.build.display.id'):
                config.version = re.match(r'.+_(\d+\.\d+\.\d+\.\d+)\(.+', getvalue(line)).group(1)
            elif line.startswith('ro.build.version.release'):
                config.sdk = getvalue(line)


def custom_kernel(file: str):
    if not file or not os.path.isfile(file):
        return
    log('自定义内核镜像')
    shutil.copy(file, 'boot/kernel')


def patch_vbmeta():
    for img in glob('vbmeta*.img', root_dir='images'):
        log(f'修补 vbmeta: {img}')
        vbmeta.patch(f'images/{img}')


def disable_avb_and_dm_verity():
    for file in glob('**/etc/fstab.*', recursive=True):
        log(f'禁用 AVB 验证引导和 Data 加密: {file}')
        with open(file, 'r+', encoding='utf-8', newline='') as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                # Remove avb
                line = re.sub(',avb=.+?,', ',', line)
                line = re.sub(',avb_keys=.+avbpubkey', '', line)
                line = re.sub(',avb_keys=.+pubkey', '', line)
                # Remove forced data encryption
                line = re.sub(',fileencryption=.+?,', ',', line)
                line = re.sub(',keydirectory=.+?,', ',', line)
                line = re.sub(',metadata_encryption=.+?,', ',', line)
                lines[i] = line
            f.seek(0)
            f.truncate()
            f.writelines(lines)


def repack_img():
    mkfs_erofs = f'{LIB_DIR}/mkfs.erofs.exe'
    magiskboot = f'{LIB_DIR}/magiskboot.exe'
    with open('config/partition_filesystem.json', 'r', encoding='utf-8') as f:
        partition_filesystem: dict = json.load(f)

    for partition in config.unpack_partitions:
        log(f'打包分区文件: {partition}')
        file = f'images/{partition}.img'
        filesystem = imgfile.FileSystem[partition_filesystem[partition]]
        match filesystem:
            case imgfile.FileSystem.EROFS:
                imgfile.sync_app_perm_and_context(partition)
                subprocess.run([mkfs_erofs, '-zlz4hc,1', '-T', '1230768000', '--mount-point', f'/{partition}',
                                '--fs-config-file', f'config/{partition}_fs_config', '--file-contexts', f'config/{partition}_file_contexts', file, partition], check=True)
            case imgfile.FileSystem.BOOT:
                os.chdir(partition)
                subprocess.run([magiskboot, 'repack', 'boot.img', f'../{file}'], check=True)
                os.chdir('..')

    log('清空 my_company 和 my_preload 分区')
    shutil.copy(f'{MISC_DIR}/BlankErofs.img', 'images/my_company.img')
    shutil.copy(f'{MISC_DIR}/BlankErofs.img', 'images/my_preload.img')


def repack_super():
    log('打包 super.img')
    cmd = [f'{LIB_DIR}/lpmake.exe',
           '--metadata-size', '65536',
           '--super-name', 'super',
           '--metadata-slots', '3',
           '--virtual-ab', '--device', f'super:{config.SUPER_SIZE}',
           '--group', f'qti_dynamic_partitions_a:{config.SUPER_SIZE}',
           '--group', f'qti_dynamic_partitions_b:{config.SUPER_SIZE}']

    for partition in config.SUPER_PARTITIONS:
        img = f'images/{partition}.img'
        size = os.path.getsize(img)
        log(f'动态分区: {partition}, 大小: {size} 字节')
        cmd += ['--partition', f'{partition}_a:readonly:{size}:qti_dynamic_partitions_a', '--image', f'{partition}_a={img}']
        cmd += ['--partition', f'{partition}_b:none:0:qti_dynamic_partitions_b']

    cmd.append('--force-full-image')
    cmd += ['--output', 'images/super.img']
    subprocess.run(cmd, check=True)

    for partition in config.SUPER_PARTITIONS:
        img = f'images/{partition}.img'
        if os.path.exists(img):
            os.remove(img)

    log('使用 zstd 压缩 super.img')
    zstd = f'{LIB_DIR}/zstd.exe'
    subprocess.run([zstd, '--rm', 'images/super.img', '-o', 'images/super.img.zst'], check=True)


def generate_script():
    log('生成刷机脚本')
    output = io.StringIO()

    for img in os.listdir('images'):
        if not img.endswith('.img'):
            continue
        partition = os.path.splitext(img)[0]
        output.write(f'flash "images/{img}" "/dev/block/bootdevice/by-name/{partition}_a"\n')
        output.write(f'flash "images/{img}" "/dev/block/bootdevice/by-name/{partition}_b"\n')
    if os.path.exists('images/super.img.zst'):
        output.write('flashZstd "images/super.img.zst" "/dev/block/bootdevice/by-name/super"\n\n')
        for item in config.SUPER_PARTITIONS:
            output.write(f'remapSuper {item}_a\n')
    var_flash_img = output.getvalue()

    remove_data_apps: set[str] = set()
    if os.path.isfile(UPDATED_APP_JSON):
        with open(UPDATED_APP_JSON, 'r', encoding='utf-8') as f:
            try:
                data: dict = json.load(f)
                remove_data_apps = data.get('rom', set())
            except json.decoder.JSONDecodeError:
                pass

    var_remove_data_app = ''
    if remove_data_apps:
        output.seek(0)
        output.truncate(0)
        output.write('\nprint "- 更新系统应用"\n')
        output.write('lookupPackagePath\n')
        for package in remove_data_apps:
            output.write(f'removeDataApp {package}\n')
        var_remove_data_app = output.getvalue()

    template_dict = {
        'var_device': config.device,
        'var_version': config.version,
        'var_sdk': config.sdk,
        'var_flash_img': var_flash_img,
        'var_remove_data_app': var_remove_data_app
    }
    template.substitute(f'{MISC_DIR}/update-binary', mapping=template_dict)


def compress_zip():
    log('构建刷机包')
    _7z = f'{LIB_DIR}/7za.exe'
    cmd = [_7z, 'a', 'tmp.zip', 'META-INF']
    for img in os.listdir('images'):
        cmd.append(f'images/{img}')

    flash_script_dir = Path('META-INF/com/google/android')
    flash_script_dir.mkdir(parents=True, exist_ok=True)
    shutil.move('update-binary', flash_script_dir.joinpath('update-binary'))
    shutil.copy(f'{MISC_DIR}/zstd', flash_script_dir.joinpath('zstd'))

    subprocess.run(cmd, check=True)

    md5 = hashlib.md5()
    with open('tmp.zip', 'rb') as f:
        md5.update(f.read())
    file_name = f'CC_{config.device}_{config.version}_{md5.hexdigest()[:10]}_{config.sdk}.zip'
    os.rename('tmp.zip', file_name)
    log(f'刷机包文件: {os.path.abspath(file_name).replace('\\', '/')}')


def make_update_module():
    log('构建系统应用更新模块')
    appupdate.run_on_module()
    if not os.path.isfile(UPDATED_APP_JSON):
        return
    customize.run_on_module()

    # Let the module manager app handle partition path automatically
    for partition in config.unpack_partitions:
        if partition != 'system' and os.path.isdir(partition):
            shutil.move(partition, f'system/{partition}')

    version_code = time.strftime('%Y%m%d')
    template.substitute(f'{MISC_DIR}/module_template/AppUpdate/module.prop', var_version=time.strftime('%Y.%m.%d'), var_version_code=version_code)
    _7z = f'{LIB_DIR}/7za.exe'
    subprocess.run([_7z, 'a', f'CC_AppUpdate_{version_code}.zip'] + os.listdir(), check=True)


def make_rom(args: argparse.Namespace):
    log('构建全量包')
    dump_payload(args.zip)
    remove_official_recovery()
    unpack_img()
    read_rom_information()
    custom_kernel(args.kernel)
    patch_vbmeta()
    disable_avb_and_dm_verity()
    handle_pangu_overlay()
    appupdate.run_on_rom()
    customize.run_on_rom()
    repack_img()
    repack_super()
    generate_script()
    compress_zip()


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('zip', help='需要处理的 ROM 包')
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='显示帮助信息')
    parser.add_argument('-k', '--kernel', help='自定义内核镜像')
    parser.add_argument('-o', '--out-dir', help='输出文件夹', type=str, default='out')
    parser.add_subparsers().add_parser('appupdate', help='打包系统应用更新模块')
    args = parser.parse_args()

    os.mkdir(args.out_dir)
    os.chdir(args.out_dir)

    start = datetime.now()
    if args.zip != 'appupdate':
        if args.kernel:
            config.unpack_partitions.add('boot')
        make_rom(args)
    else:
        make_update_module()
    result = datetime.now() - start
    log(f'已完成, 耗时 {int(result.seconds / 60)} 分 {result.seconds % 60} 秒')


if __name__ == '__main__':
    main()
