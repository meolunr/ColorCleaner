import io
import os
import re
import shutil
import subprocess
from enum import Enum, auto
from pathlib import Path

import ccglobal

_MAGISKBOOT = f'{ccglobal.LIB_DIR}/magiskboot.exe'
_EXTRACT_EROFS = f'{ccglobal.LIB_DIR}/extract.erofs.exe'
_MKFS_EROFS = f'{ccglobal.LIB_DIR}/mkfs.erofs.exe'
_E2FS_TOOL = f'{ccglobal.LIB_DIR}/e2fstool.exe'


class FileSystem(Enum):
    BOOT = auto()
    EROFS = auto()
    EXT4 = auto()
    F2FS = auto()


_FS_TYPES = (
    (FileSystem.BOOT, 0, b'ANDROID!'),
    (FileSystem.EROFS, 1024, b'\xe2\xe1\xf5\xe0'),
    (FileSystem.EXT4, 1024 + 0x38, b'\123\357'),
    (FileSystem.F2FS, 1024, b'\x10\x20\xf5\xf2')
)


def unpack(file: str, partition: str, out_dir: str = '.'):
    out_dir = os.path.relpath(out_dir)
    Path(out_dir).joinpath('config').mkdir(exist_ok=True)

    fs_type = _filesystem(file)
    with open(f'{out_dir}/config/{partition}_fs_type', 'w', encoding='utf-8') as f:
        f.write(fs_type.name)

    ccglobal.log(f'提取镜像: {file}, 格式: {fs_type}')
    match fs_type:
        case FileSystem.EROFS:
            subprocess.run([_EXTRACT_EROFS, '-x', '-i', file, '-o', out_dir], check=True)
        case FileSystem.EXT4:
            subprocess.run([_E2FS_TOOL, file, f'{out_dir}/{partition}'], check=True)
        case FileSystem.BOOT:
            cwd = os.getcwd()
            partition_dir = f'{out_dir}/{partition}'
            os.mkdir(partition_dir)
            shutil.copy(file, f'{partition_dir}/{partition}.img')
            os.chdir(partition_dir)
            subprocess.run([_MAGISKBOOT, 'unpack', f'{partition}.img'], check=True)
            os.chdir(cwd)


def repack(file: str, partition: str, out_dir: str = '.'):
    out_dir = os.path.relpath(out_dir)

    with open(f'{out_dir}/config/{partition}_fs_type', 'r', encoding='utf-8') as f:
        fs_type = FileSystem[f.read()]

    ccglobal.log(f'打包镜像: {file}, 格式: {fs_type}')
    match fs_type:
        case FileSystem.EROFS:
            subprocess.run([_MKFS_EROFS, '-zlz4hc,1', '-T', '1230768000', '--mount-point', f'/{partition}', '--fs-config-file', f'{out_dir}/config/{partition}_fs_config',
                            '--file-contexts', f'{out_dir}/config/{partition}_file_contexts', file, f'{out_dir}/{partition}'], check=True)
        case FileSystem.BOOT:
            cwd = os.getcwd()
            os.chdir(f'{out_dir}/{partition}')
            subprocess.run([_MAGISKBOOT, 'repack', f'{partition}.img', f'{cwd}/{file}'], check=True)
            os.chdir(cwd)


def sync_app_perm_and_context(partition: str, out_dir: str = '.'):
    out_dir = os.path.relpath(out_dir)

    if partition == 'system':
        app = f'system/system/app'
        priv_app = f'system/system/priv-app'
    else:
        app = f'{partition}/app'
        priv_app = f'{partition}/priv-app'
    if not os.path.exists(f'{out_dir}/{app}') and not os.path.exists(f'{out_dir}/{priv_app}'):
        return

    existing = set()
    with open(f'{out_dir}/config/{partition}_fs_config', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith(app) or line.startswith(priv_app):
                existing.add(line.split(' ')[0])

    mode_output = io.StringIO()
    context_output = io.StringIO()
    for folder in (app, priv_app):
        for root, dirs, files in os.walk(f'{out_dir}/{folder}'):
            for i in dirs:
                i = os.path.join(os.path.relpath(root), i).replace('\\', '/')
                if i not in existing:
                    mode_output.write(f'{i} 0 0 0755\n')
                    context_output.write(f'/{re.escape(i)} u:object_r:system_file:s0\n')
            for i in files:
                i = os.path.join(os.path.relpath(root), i).replace('\\', '/')
                if i not in existing:
                    mode_output.write(f'{i} 0 0 0644\n')
                    context_output.write(f'/{re.escape(i)} u:object_r:system_file:s0\n')

    if partition == 'product':
        mode_output.write(f'product/UpdatedApp.json 0 0 0644\n')
        context_output.write('/product/UpdatedApp\\.json u:object_r:system_file:s0\n')

    with open(f'{out_dir}/config/{partition}_fs_config', 'a', encoding='utf-8') as f:
        f.write(mode_output.getvalue())
    with open(f'{out_dir}/config/{partition}_file_contexts', 'a', encoding='utf-8') as f:
        f.write(context_output.getvalue())


def _filesystem(file: str) -> FileSystem | None:
    with open(file, 'rb') as f:
        for fs, offset, magic in _FS_TYPES:
            f.seek(offset, os.SEEK_SET)
            buf = f.read(len(magic))
            if buf == magic:
                return fs
    return None
