import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import time
from glob import glob
from pathlib import Path

import appupdate
import ccglobal
import config
import customize
import vbmeta
from util import imgfile, template


def dump_payload(file: str):
    ccglobal.log(f'解压 Payload: {file}')
    payload_extract = f'{ccglobal.LIB_DIR}/payload_extract.exe'
    subprocess.run([payload_extract, '-x', '-i', file, '-o', 'images'], check=True)


def remove_official_recovery():
    ccglobal.log('去除官方 Recovery')
    recovery = Path('images/recovery.img')
    recovery.unlink(True)


def unpack_img():
    extract_erofs = f'{ccglobal.LIB_DIR}/extract.erofs.exe'
    magiskboot = f'{ccglobal.LIB_DIR}/magiskboot.exe'
    partition_filesystem = {}

    for partition in config.UNPACK_PARTITIONS:
        img = f'{partition}.img'
        file = f'images/{img}'
        filesystem = imgfile.filesystem(file)
        ccglobal.log(f'提取分区文件: {img}, 格式: {filesystem}')
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
    with open(ccglobal.PARTITION_FILESYSTEM_JSON, 'w', encoding='utf-8') as f:
        json.dump(partition_filesystem, f, indent=4)


def read_rom_information():
    with open('product/etc/build.prop', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('ro.product.product.name='):
                ccglobal.device = ccglobal.get_prop_value(line)
            elif line.startswith('ro.product.build.version.incremental='):
                ccglobal.version = re.match(r'OS(\d+\.\d+\.\d+\.\d+)\..+', ccglobal.get_prop_value(line)).group(1)
            elif line.startswith('ro.product.build.version.release='):
                ccglobal.sdk = ccglobal.get_prop_value(line)

    pattern = re.compile(r'.*?(\d+\.\d+).+?-(android\d+)')
    with open('boot/kernel', 'rb') as f:
        for item in f.read().split(b'\x00'):
            try:
                item = item.decode('utf-8')
            except UnicodeDecodeError:
                continue
            if all(c.isascii() and (c.isprintable() and c != '\t' and c != '\n' or c == ' ') for c in item):
                match = pattern.search(item)
                if match:
                    ccglobal.kmi = f'{match.group(2)}-{match.group(1)}'
                    break


def custom_kernel(file: str):
    if not file or not os.path.isfile(file):
        return
    ccglobal.log('自定义内核镜像')
    shutil.copy(file, 'boot/kernel')


def install_lkm(no_lkm: bool):
    if no_lkm:
        return
    ccglobal.log('安装 KernelSU LKM')

    ksud = f'{ccglobal.LIB_DIR}/ksud.exe'
    magiskboot = f'{ccglobal.LIB_DIR}/magiskboot.exe'
    subprocess.run([ksud, 'boot-patch', '--magiskboot', magiskboot, '-b', 'images/init_boot.img', '--kmi', ccglobal.kmi, '--out-name', 'images/init_boot.img'], check=True)


def patch_vbmeta():
    for img in glob('vbmeta*.img', root_dir='images'):
        ccglobal.log(f'修补 vbmeta: {img}')
        vbmeta.patch(f'images/{img}', 'images/boot.img')


def disable_avb_and_dm_verity():
    for file in glob('**/etc/fstab.*', recursive=True):
        ccglobal.log(f'禁用 AVB 验证引导和 Data 加密: {file}')
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


def handle_pangu_overlay():
    if not os.path.isdir('product/pangu'):
        return
    ccglobal.log('处理盘古架构')
    lines = []
    with open('config/product_file_contexts', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('/product/pangu'):
                splits = line.split(' ')
                path = splits[0][14:]
                if not os.path.exists(f'system{path}'):
                    lines.append(f'/system{path} {splits[1]}')
    with open('config/system_file_contexts', 'a', encoding='utf-8', newline='') as f:
        f.writelines(lines)

    lines.clear()
    with open('config/product_fs_config', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('product/pangu'):
                pos = line.index(' ')
                path = line[:pos][13:]
                if not os.path.exists(f'system{path}'):
                    lines.append(f'system{path}{line[pos:]}')
    with open('config/system_fs_config', 'a', encoding='utf-8', newline='') as f:
        f.writelines(lines)


def repack_img():
    mkfs_erofs = f'{ccglobal.LIB_DIR}/mkfs.erofs.exe'
    magiskboot = f'{ccglobal.LIB_DIR}/magiskboot.exe'
    with open(ccglobal.PARTITION_FILESYSTEM_JSON, 'r', encoding='utf-8') as f:
        partition_filesystem: dict = json.load(f)

    for partition in config.UNPACK_PARTITIONS:
        ccglobal.log(f'打包分区文件: {partition}')
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

    ccglobal.log('清空 cust 分区')
    shutil.copy(f'{ccglobal.MISC_DIR}/BlankErofs.img', 'images/cust.img')


def repack_super():
    ccglobal.log('打包 super.img')
    cmd = [f'{ccglobal.LIB_DIR}/lpmake.exe',
           '--metadata-size', '65536',
           '--super-name', 'super',
           '--metadata-slots', '3',
           '--virtual-ab', '--device', f'super:{config.SUPER_SIZE}',
           '--group', f'qti_dynamic_partitions_a:{config.SUPER_SIZE}',
           '--group', f'qti_dynamic_partitions_b:{config.SUPER_SIZE}']

    for partition in config.SUPER_PARTITIONS:
        img = f'images/{partition}.img'
        size = os.path.getsize(img)
        ccglobal.log(f'动态分区: {partition}, 大小: {size} 字节')
        cmd += ['--partition', f'{partition}_a:readonly:{size}:qti_dynamic_partitions_a', '--image', f'{partition}_a={img}']
        cmd += ['--partition', f'{partition}_b:none:0:qti_dynamic_partitions_b']

    cmd.append('--force-full-image')
    cmd += ['--output', 'images/super.img']
    subprocess.run(cmd, check=True)

    for partition in config.SUPER_PARTITIONS:
        img = f'images/{partition}.img'
        if os.path.exists(img):
            os.remove(img)

    ccglobal.log('使用 zstd 压缩 super.img')
    zstd = f'{ccglobal.LIB_DIR}/zstd.exe'
    subprocess.run([zstd, '--rm', 'images/super.img', '-o', 'images/super.img.zst'], check=True)


def generate_script():
    ccglobal.log('生成刷机脚本')
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
    if os.path.isfile(ccglobal.UPDATED_APP_JSON):
        with open(ccglobal.UPDATED_APP_JSON, 'r', encoding='utf-8') as f:
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
        'var_device': ccglobal.device,
        'var_version': ccglobal.version,
        'var_sdk': ccglobal.sdk,
        'var_flash_img': var_flash_img,
        'var_remove_data_app': var_remove_data_app
    }
    template.substitute(f'{ccglobal.MISC_DIR}/update-binary', mapping=template_dict)


def compress_zip():
    ccglobal.log('构建全量包')
    _7z = f'{ccglobal.LIB_DIR}/7za.exe'
    cmd = [_7z, 'a', 'tmp.zip', 'META-INF']
    for img in os.listdir('images'):
        cmd.append(f'images/{img}')

    flash_script_dir = Path('META-INF/com/google/android')
    flash_script_dir.mkdir(parents=True, exist_ok=True)
    shutil.move('update-binary', flash_script_dir.joinpath('update-binary'))
    shutil.copy(f'{ccglobal.MISC_DIR}/zstd', flash_script_dir.joinpath('zstd'))

    subprocess.run(cmd, check=True)

    md5 = hashlib.md5()
    with open('tmp.zip', 'rb') as f:
        md5.update(f.read())
    filename = f'HC_{ccglobal.device}_{ccglobal.version}_{md5.hexdigest()[:10]}.zip'
    os.rename('tmp.zip', filename)
    ccglobal.log(f'全量包文件: {os.path.abspath(filename).replace('\\', '/')}')


def make_module():
    ccglobal.log('构建系统更新模块')
    appupdate.run_on_module()
    if not os.path.isdir('product'):
        return
    customize.run_on_module()

    # Let the module manager app handle partition path automatically
    for partition in config.UNPACK_PARTITIONS:
        if partition != 'system' and os.path.isdir(partition):
            shutil.move(partition, f'system/{partition}')

    template_dir = Path(f'{ccglobal.MISC_DIR}/module_template/Patch')
    shutil.copy(template_dir.joinpath('post-fs-data.sh'), os.getcwd())

    version_code = time.strftime('%Y%m%d')
    version_name = version_code
    template.substitute(template_dir.joinpath('module.prop'), var_version_code=version_code, var_version=version_name)

    _7z = f'{ccglobal.LIB_DIR}/7za.exe'
    subprocess.run([_7z, 'a', f'CC_Patch_{version_name}.zip', 'module.prop', 'system', 'customize.sh', 'post-fs-data.sh'], check=True)


def make_rom(args: argparse.Namespace):
    ccglobal.log('构建全量包')
    dump_payload(args.file)
    remove_official_recovery()
    unpack_img()
    read_rom_information()
    custom_kernel(args.kernel)
    install_lkm(args.no_lkm)
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
    parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='显示帮助信息')
    subparsers = parser.add_subparsers(dest='command', required=True)

    rom_parser = argparse.ArgumentParser(add_help=False)
    rom_parser.add_argument('file', help='需要处理的 ROM 包')
    rom_parser.add_argument('-k', '--kernel', help='自定义内核镜像')
    rom_parser.add_argument('--no-lkm', action='store_true', help='不安装 KernelSU LKM')

    out_parser = argparse.ArgumentParser(add_help=False)
    out_parser.add_argument('-o', '--out-dir', help='输出文件夹', default='out')
    out_parser.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS, help='显示帮助信息')

    subparsers.add_parser('rom', help='构建全量包', parents=[rom_parser, out_parser], add_help=False)
    subparsers.add_parser('module', help='构建系统更新模块', parents=[out_parser], add_help=False)
    args = parser.parse_args()

    os.mkdir(args.out_dir)
    os.chdir(args.out_dir)

    start = time.time()
    match args.command:
        case 'rom':
            make_rom(args)
        case 'module':
            make_module()
    result = time.time() - start
    ccglobal.log(f'已完成, 耗时 {int(result / 60)} 分 {int(result % 60)} 秒')


if __name__ == '__main__':
    main()
