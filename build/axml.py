import os
import struct
from io import BytesIO


class Chunk:
    SIZE = 8
    _FORMAT_STRING = '<2HI'  # type, header size, size (chunk)

    def __init__(self, f: BytesIO):
        (self.type, self.header_size, self.size) = struct.unpack(self._FORMAT_STRING, f.read(self.SIZE))


class StringChunk(Chunk):
    _FORMAT_STRING = ('<2I'  # string count, style count
                      '2H'  # utf-8, sorted (flags)
                      '2I')  # strings start, styles start

    def __init__(self, f: BytesIO):
        super().__init__(f)
        buff = f.read(struct.calcsize(self._FORMAT_STRING))
        (self.string_count, _, self._flag_utf8, _, self.strings_start, _) = struct.unpack(self._FORMAT_STRING, buff)
        self.is_utf8 = self._flag_utf8 != 0

        self.string_offsets = []
        for i in range(self.string_count):
            self.string_offsets.append(struct.unpack('<I', f.read(4))[0])

        self.string_pool = f.read(self.size - self.strings_start)


class StartNamespaceChunk(Chunk):
    _FORMAT_STRING = ('<2I'  # line number, comment
                      '2I')  # prefix, uri (namespace)

    def __init__(self, f: BytesIO):
        super().__init__(f)
        buff = f.read(struct.calcsize(self._FORMAT_STRING))
        (_, _, self.prefix, self.uri) = struct.unpack(self._FORMAT_STRING, buff)


class StartTagChunk(Chunk):
    TYPE = 0x102
    _FORMAT_STRING = ('<2I'  # line number, comment
                      '2I'  # namespace uri, name
                      '3H'  # start, size, count (attribute)
                      '3H')  # id index, class index, style index

    class Attribute:
        SIZE = 20
        _FORMAT_STRING = ('<3I'  # namespace uri, name, raw value
                          'H2BI')  # size, res0, data type, data
        DATA_TYPE_REFERENCE = 0x01
        DATA_TYPE_STRING = 0x03
        DATA_TYPE_BOOLEAN = 0x12

        def __init__(self, f: BytesIO):
            buff = f.read(struct.calcsize(self._FORMAT_STRING))
            (self.namespace_uri, self.name, _, _, _, self.data_type, self.data) = struct.unpack(self._FORMAT_STRING, buff)

    def __init__(self, f: BytesIO):
        super().__init__(f)
        buff = f.read(struct.calcsize(self._FORMAT_STRING))
        (_, _, self.namespace_uri, self.name, _, _, self.attribute_count, _, _, _) = struct.unpack(self._FORMAT_STRING, buff)

    def read_attribute(self, f: BytesIO):
        attributes = []
        for i in range(self.attribute_count):
            attributes.append(StartTagChunk.Attribute(f))
        return attributes


class ManifestXml:
    def __init__(self, data: bytes):
        self.attributes = {}

        with BytesIO(data) as f:
            f.seek(Chunk.SIZE)
            self.string_chunk = StringChunk(f)
            self._string_cache = {}

            # Skip resource map chunk
            f.seek(Chunk(f).size - Chunk.SIZE, os.SEEK_CUR)

            self.start_namespace_chunk = StartNamespaceChunk(f)
            self._namespace_map = {self.start_namespace_chunk.uri: self.start_namespace_chunk.prefix}

            length = len(data)
            while f.tell() < length:
                chunk = Chunk(f)
                if chunk.type != StartTagChunk.TYPE:
                    f.seek(chunk.size - Chunk.SIZE, os.SEEK_CUR)
                    continue

                f.seek(-Chunk.SIZE, os.SEEK_CUR)
                chunk = StartTagChunk(f)
                name = self._get_string(chunk.name)
                # Only parse these elements because we need their attributes
                if name not in ('manifest', 'application'):
                    # Skip attributes of start tag
                    f.seek(chunk.attribute_count * StartTagChunk.Attribute.SIZE, os.SEEK_CUR)
                    continue

                attributes = chunk.read_attribute(f)
                self._parse_attribute(name, attributes)

    def _parse_attribute(self, name: str, attributes: list[StartTagChunk.Attribute]):
        match name:
            case 'manifest':
                pass
            case _:
                self.attributes[name] = {}

        for attribute in attributes:
            # resources.arsc not parsed
            if attribute.data_type == StartTagChunk.Attribute.DATA_TYPE_REFERENCE:
                continue

            prefix = self._get_prefix(attribute.namespace_uri)
            match attribute.data_type:
                case StartTagChunk.Attribute.DATA_TYPE_STRING:
                    attribute.data = self._get_string(attribute.data)
                case StartTagChunk.Attribute.DATA_TYPE_BOOLEAN:
                    attribute.data = attribute.data != 0

            key = f'{prefix}{self._get_string(attribute.name)}'
            match name:
                case 'manifest':
                    self.attributes[key] = attribute.data
                case _:
                    self.attributes[name][key] = attribute.data

    def _get_string(self, idx: int):
        if idx in self._string_cache:
            return self._string_cache[idx]

        offset = self.string_chunk.string_offsets[idx]
        chars_start = offset + 2
        if self.string_chunk.is_utf8:
            struct_size = 1  # Skip byte length
            format_string = '<B'
            encoding = 'utf-8'
        else:
            struct_size = 2
            format_string = '<H'
            encoding = 'utf-16'
        char_num = struct.unpack(format_string, self.string_chunk.string_pool[offset: offset + struct_size])[0]
        chars = self.string_chunk.string_pool[chars_start: chars_start + char_num * struct_size].decode(encoding)
        self._string_cache[idx] = chars
        return chars

    def _get_prefix(self, uri: int):
        if uri == 0xFFFFFFFF:
            return ''
        return f'{self._get_string(self._namespace_map[uri])}:'
