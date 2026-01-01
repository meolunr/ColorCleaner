import subprocess

import ccglobal


def decode(file: str, output: str, resource_type: str = 'xml'):
    subprocess.run(['java', '-jar', f'{ccglobal.LIB_DIR}/APKEditor.jar', 'd', '-t', resource_type, '-i', file, '-o', output], stderr=subprocess.STDOUT)


def build(dir_path: str, output: str):
    subprocess.run(['java', '-jar', f'{ccglobal.LIB_DIR}/APKEditor.jar', 'b', '-f', '-i', dir_path, '-o', output], stderr=subprocess.STDOUT)


def refactor(file: str, output: str):
    subprocess.run(['java', '-jar', f'{ccglobal.LIB_DIR}/APKEditor.jar', 'x', '-i', file, '-o', output], stderr=subprocess.STDOUT)
