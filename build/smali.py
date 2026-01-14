import re
from enum import Enum


class MethodSpecifier:
    class Access(Enum):
        PUBLIC = 'public'
        PROTECTED = 'protected'
        PRIVATE = 'private'
        DEFAULT = ''

    def __init__(self):
        self.access = None
        self.is_static = None
        self.is_final = None
        self.is_abstract = None
        self.name = None
        self.parameters = None
        self.return_type = None
        self.keywords: set[str] = set()


class SmaliFile:
    def __init__(self, file: str):
        self.file = file
        self._methods: dict[MethodSpecifier, str] = {}
        self._constructors: dict[MethodSpecifier, str] = {}

        with open(self.file, 'r', encoding='utf-8') as f:
            pattern = re.compile(r'(\.method (public|protected|private|)(.*?)(\S+)\((\S*?)\)(\S+?)\n.+?\.end method)', re.DOTALL)
            for method_defines in re.findall(pattern, f.read()):
                if ' constructor ' in method_defines[2]:
                    self._parse_constructor(method_defines)
                else:
                    self._parse_method(method_defines)

    def find_method(self, specifier: MethodSpecifier) -> str | None:
        results = self._methods.keys()
        conditions = {
            lambda x: True if specifier.name is None else x.name == specifier.name,
            lambda x: True if specifier.access is None else x.access == specifier.access,
            lambda x: True if specifier.is_static is None else x.is_static == specifier.is_static,
            lambda x: True if specifier.is_final is None else x.is_final == specifier.is_final,
            lambda x: True if specifier.is_abstract is None else x.is_abstract == specifier.is_abstract,
            lambda x: True if specifier.parameters is None else x.parameters == specifier.parameters,
            lambda x: True if specifier.return_type is None else x.return_type == specifier.return_type
        }
        for condition in conditions:
            results = set(filter(condition, results))
        if specifier.keywords:
            results = set(filter(self._filter_keywords(specifier.keywords), results))

        if len(results) == 1:
            return self._methods[results.pop()]
        else:
            return None

    def find_constructor(self, parameters: str = ''):
        results = self._constructors.keys()
        results = set(filter(lambda x: x.parameters == parameters, results))

        if len(results) == 1:
            return self._constructors[results.pop()]
        else:
            return None

    def method_replace(self, old_method: str | MethodSpecifier, new_body: str):
        if type(old_method) is MethodSpecifier:
            old_method = self.find_method(old_method)
        with open(self.file, 'r+', encoding='utf-8') as file:
            text = file.read().replace(old_method, new_body)
            file.seek(0)
            file.truncate()
            file.write(text)

    def method_return_boolean(self, specifier: MethodSpecifier, value: bool):
        self.method_return_int(specifier, int(value))

    def method_return_int(self, specifier: MethodSpecifier, value: int):
        if -8 <= value < 8:
            const_instruction = 'const/4'
        elif -32768 <= value < 32768:
            const_instruction = 'const/16'
        else:
            const_instruction = 'const'

        old_body = self.find_method(specifier)
        new_body = old_body.splitlines()[0] + f'''
    .locals 1

    {const_instruction} v0, {hex(value)}

    return v0
.end method\
'''
        self.method_replace(old_body, new_body)

    def method_return_null(self, specifier: MethodSpecifier):
        old_body = self.find_method(specifier)
        new_body = old_body.splitlines()[0] + f'''
    .locals 1

    const/4 v0, 0x0

    return-object v0
.end method\
'''
        self.method_replace(old_body, new_body)

    def method_nop(self, specifier: MethodSpecifier):
        old_body = self.find_method(specifier)
        new_body = old_body.splitlines()[0] + '''
    .locals 0

    return-void
.end method\
'''
        self.method_replace(old_body, new_body)

    def method_insert_before(self, specifier: MethodSpecifier, insert: str):
        old_body = self.find_method(specifier)

        keyword_index = 0
        for item in ('.locals', '.end annotation', '.end param'):
            pos = old_body.find(item, keyword_index)
            if pos > keyword_index:
                keyword_index = pos
        index = old_body.find('\n', keyword_index) + 1

        new_body = old_body[:index] + f'\n{insert}' + old_body[index:]
        self.method_replace(old_body, new_body)

    def get_type_signature(self):
        normpath = self.file.replace('\\', '/')
        return re.sub(r'.+?/smali/classes\d*/(.+?)(?:\.1)*\.smali', r'L\g<1>;', normpath)

    def _parse_method(self, method_defines: tuple[str, ...]):
        specifier = MethodSpecifier()
        specifier.access = MethodSpecifier.Access(method_defines[1])
        specifier.is_static = ' static ' in method_defines[2]
        specifier.is_final = ' final ' in method_defines[2]
        specifier.is_abstract = ' abstract ' in method_defines[2]
        specifier.name = method_defines[3]
        specifier.parameters = method_defines[4]
        specifier.return_type = method_defines[5]

        self._methods[specifier] = method_defines[0]

    def _parse_constructor(self, method_defines: tuple[str, ...]):
        specifier = MethodSpecifier()
        specifier.parameters = method_defines[4]

        self._constructors[specifier] = method_defines[0]

    def _filter_keywords(self, keywords):
        def condition(specifier: MethodSpecifier):
            body = self._methods[specifier]
            return all(x in body for x in keywords)

        return condition
