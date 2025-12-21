import os
import shutil
from glob import glob
from pathlib import Path
from zipfile import ZipFile

from util import apkeditor
from .axml import ManifestXml
from .smali import SmaliFile
from .xml import XmlFile


class ApkFile:
    def __init__(self, file: str):
        self.file = file
        self.output = f'{self.file}.out'
        self._manifest_attributes = None

    def decode(self, no_res=True):
        if no_res:
            apkeditor.decode(self.file, self.output, 'raw')
        else:
            apkeditor.decode(self.file, self.output)

    def build(self):
        apkeditor.build(self.output, self.file)
        shutil.rmtree(self.output)

    def refactor(self):
        old_file = f'{self.file}.old'
        os.rename(self.file, old_file)
        apkeditor.refactor(old_file, self.file)
        os.remove(old_file)

    def open_smali(self, file: str):
        dirs = set(map(lambda x: f'smali/{x}', os.listdir(f'{self.output}/smali')))
        for dir_name in dirs:
            assumed_path = f'{self.output}/{dir_name}/{file}'
            if os.path.exists(assumed_path):
                return SmaliFile(assumed_path)
        return None

    def find_smali(self, *keywords: str):
        results = set[SmaliFile]()
        # See: https://docs.python.org/3/using/windows.html#removing-the-max-path-limitation
        for file in glob(f'{self.output}/smali*/**/*.smali', recursive=True):
            keyword_set = set(keywords)
            with open(file, 'r', encoding='utf-8') as f:
                for line in f:
                    for keyword in keywords:
                        if keyword in line:
                            keyword_set.discard(keyword)
            if len(keyword_set) == 0:
                results.add(SmaliFile(file))
        return results

    def add_smali(self, src_path: str, full_smali_path: str):
        smali_dir = sorted(os.listdir(f'{self.output}/smali'), reverse=True)[0]
        dst_path = Path(f'{self.output}/smali/{smali_dir}/{full_smali_path}')
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src_path, dst_path)

    def open_xml(self, file: str):
        return XmlFile(f'{self.output}/resources/package_1/res/{file}')

    def version_code(self):
        if not self._manifest_attributes:
            self._parse_manifest()
        return self._manifest_attributes['android:versionCode']

    def extract_native_libs(self) -> bool | None:
        if not self._manifest_attributes:
            self._parse_manifest()
        return self._manifest_attributes['application'].get('android:extractNativeLibs', None)

    def _parse_manifest(self):
        with ZipFile(self.file, 'r') as zip_file:
            f = zip_file.open('AndroidManifest.xml', 'r')
            self._manifest_attributes = ManifestXml(f.read()).attributes
