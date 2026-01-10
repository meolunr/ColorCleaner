import os
import struct


def round_to_multiple(number, size):
    remainder = number % size
    if remainder == 0:
        return number
    return number + size - remainder


class AvbHeader:
    SIZE = 256
    FLAG_DISABLE_VERITY = 0x1
    FLAG_DISABLE_VERIFICATION = 0x2
    _MAGIC = b'AVB0'
    _RESERVED = 80
    # @formatter:off
    _FORMAT_STRING = ('!4s'                  # magic
                      '2L'                   # avb version
                      '2Q'                   # 2 * block size
                      'L'                    # algorithm type
                      '2Q'                   # offset, size (hash)
                      '2Q'                   # offset, size (signature)
                      '2Q'                   # offset, size (public key)
                      '2Q'                   # offset, size (public key metadata)
                      '2Q'                   # offset, size (descriptors)
                      'Q'                    # rollback index
                      'L'                    # flags
                      'L'                    # rollback index location
                      '47sx' +               # NUL-terminated release string
                      str(_RESERVED) + 'x')  # padding for reserved bytes
    # @formatter:on

    def __init__(self, data: bytes):
        (self.magic, self.avb_version_major, self.avb_version_minor,
         self.authentication_data_block_size, self.auxiliary_data_block_size,
         self.algorithm_type,
         self.hash_offset, self.hash_size,
         self.signature_offset, self.signature_size,
         self.public_key_offset, self.public_key_size,
         self.public_key_metadata_offset, self.public_key_metadata_size,
         self.descriptors_offset, self.descriptors_size,
         self.rollback_index, self.flags, self.rollback_index_location, release_string) = struct.unpack(self._FORMAT_STRING, data)
        self.release_string = release_string.rstrip(b'\0').decode('utf-8')

    def encode(self):
        release_string_encoded = self.release_string.encode('utf-8')
        return struct.pack(self._FORMAT_STRING,
                           self.magic, self.avb_version_major, self.avb_version_minor,
                           self.authentication_data_block_size, self.auxiliary_data_block_size,
                           self.algorithm_type,
                           self.hash_offset, self.hash_size,
                           self.signature_offset, self.signature_size,
                           self.public_key_offset, self.public_key_size,
                           self.public_key_metadata_offset, self.public_key_metadata_size,
                           self.descriptors_offset, self.descriptors_size,
                           self.rollback_index, self.flags, self.rollback_index_location, release_string_encoded)


class AvbDescriptor:
    _HEADER_SIZE = 16
    _FORMAT_STRING = '!2Q'  # tag, num_bytes_following (descriptor header)

    def __init__(self, data):
        (self.tag, num_bytes_following) = struct.unpack(self._FORMAT_STRING, data[0:self._HEADER_SIZE])
        self.data = data[self._HEADER_SIZE:self._HEADER_SIZE + num_bytes_following]

    def encode(self):
        num_bytes_following = len(self.data)
        nbf_with_padding = round_to_multiple(num_bytes_following, 8)
        padding_size = nbf_with_padding - num_bytes_following
        desc = struct.pack(self._FORMAT_STRING, self.tag, nbf_with_padding)
        padding = struct.pack(str(padding_size) + 'x')
        ret = desc + self.data + padding
        return bytearray(ret)


class AvbPropertyDescriptor:
    TAG = 0
    _HEADER_SIZE = 32
    # @formatter:off
    _FORMAT_STRING = ('!QQ'  # tag, num_bytes_following (descriptor header)
                      'Q'    # key size (bytes)
                      'Q')   # value size (bytes)
    # @formatter:on

    def __init__(self, data):
        (tag, num_bytes_following, key_size, value_size) = struct.unpack(self._FORMAT_STRING, data[0:self._HEADER_SIZE])
        key_offset = self._HEADER_SIZE
        value_offset = key_offset + key_size + 1
        self.key = data[key_offset:(key_offset + key_size)].decode('utf-8')
        self.value = data[value_offset:value_offset + value_size]

    def encode(self):
        key_encoded = self.key.encode('utf-8')
        num_bytes_following = (self._HEADER_SIZE + len(key_encoded) + len(self.value) + 2 - 16)
        nbf_with_padding = round_to_multiple(num_bytes_following, 8)
        padding_size = nbf_with_padding - num_bytes_following
        desc = struct.pack(self._FORMAT_STRING, self.TAG, nbf_with_padding, len(key_encoded), len(self.value))
        return desc + key_encoded + b'\0' + self.value + b'\0' + padding_size * b'\0'


class VbMeta:
    def __init__(self, file: str):
        self.file = file
        self._image_size = os.path.getsize(file)
        with open(file, 'rb') as self._image:
            vbmeta_offset = 0
            # Check avb footer
            self._image.seek(-64, os.SEEK_END)
            if self._image.read(4) == b'AVBf':
                self._image.seek(16, os.SEEK_CUR)
                vbmeta_offset = int.from_bytes(self._image.read(8))

            self._read_header(vbmeta_offset)

            self._image.seek(vbmeta_offset + AvbHeader.SIZE)
            self.authentication_data_blob = self._image.read(self.header.authentication_data_block_size)

            aux_block_offset = vbmeta_offset + AvbHeader.SIZE + self.header.authentication_data_block_size
            desc_start_offset = aux_block_offset + self.header.descriptors_offset
            self._read_descriptors(desc_start_offset)

            self._image.seek(vbmeta_offset + AvbHeader.SIZE + self.header.authentication_data_block_size + self.header.public_key_offset)
            self.public_key_blob = self._image.read(self.header.public_key_size)
            self._image.seek(vbmeta_offset + AvbHeader.SIZE + self.header.authentication_data_block_size + self.header.public_key_metadata_offset)
            self.public_key_metadata_blob = self._image.read(self.header.public_key_metadata_size)

    def write(self):
        with open(self.file, 'wb') as f:
            f.write(self._encode())

    def _read_header(self, offset):
        self._image.seek(offset)
        data = self._image.read(AvbHeader.SIZE)
        self.header = AvbHeader(data)

    def _read_descriptors(self, offset):
        self._image.seek(offset)
        data = self._image.read(self.header.descriptors_size)

        self.descriptors = []
        desc_offset = 0
        while desc_offset < len(data):
            tag, nb_following = struct.unpack('!2Q', data[desc_offset:desc_offset + 16])
            if tag == AvbPropertyDescriptor.TAG:
                clazz = AvbPropertyDescriptor
            else:
                clazz = AvbDescriptor
            self.descriptors.append(clazz(data[desc_offset:desc_offset + 16 + nb_following]))
            desc_offset += 16 + nb_following

    def _encode(self):
        descriptors_blob = bytearray()
        for item in self.descriptors:
            descriptors_blob.extend(item.encode())

        aux_data_blob = bytearray()
        aux_data_blob.extend(descriptors_blob)
        aux_data_blob.extend(self.public_key_blob)
        aux_data_blob.extend(self.public_key_metadata_blob)

        self.header.authentication_data_block_size = len(self.authentication_data_blob)
        self.header.auxiliary_data_block_size = round_to_multiple(len(aux_data_blob), 64)
        self.header.descriptors_size = len(descriptors_blob)
        self.header.public_key_offset = self.header.descriptors_size
        self.header.public_key_size = len(self.public_key_blob)
        self.header.public_key_metadata_offset = self.header.public_key_offset + self.header.public_key_size
        self.header.public_key_metadata_size = len(self.public_key_metadata_blob)

        padding_bytes = self.header.auxiliary_data_block_size - len(aux_data_blob)
        aux_data_blob.extend(b'\0' * padding_bytes)

        vbmeta_blob = bytearray()
        vbmeta_blob.extend(self.header.encode())
        vbmeta_blob.extend(self.authentication_data_blob)
        vbmeta_blob.extend(aux_data_blob)
        vbmeta_size = len(vbmeta_blob)
        padded_size = round_to_multiple(vbmeta_size, self._image_size)
        padding_bytes = padded_size - vbmeta_size
        vbmeta_blob.extend(b'\0' * padding_bytes)

        return vbmeta_blob


def patch(vbmeta_file: str, boot_file: str):
    avb = VbMeta(vbmeta_file)

    avb.header.algorithm_type = 0
    avb.header.rollback_index = 0
    avb.public_key_blob = bytes()
    avb.public_key_metadata_blob = bytes()
    avb.header.flags = AvbHeader.FLAG_DISABLE_VERITY | AvbHeader.FLAG_DISABLE_VERIFICATION

    # Copy avb property descriptors from boot.img
    if os.path.basename(vbmeta_file) == 'vbmeta.img':
        for desc in VbMeta(boot_file).descriptors:
            if not isinstance(desc, AvbPropertyDescriptor):
                continue
            match desc.key:
                case 'com.android.build.boot.os_version':
                    avb.descriptors.insert(0, desc)
                case 'com.android.build.boot.fingerprint':
                    avb.descriptors.insert(1, desc)
                case 'com.android.build.boot.security_patch':
                    avb.descriptors.insert(2, desc)

    existing = set()
    for desc in avb.descriptors[:]:
        # Remove chain, hash and hashtree descriptors
        if getattr(desc, 'tag', -1) in (1, 2, 4):
            avb.descriptors.remove(desc)
        elif isinstance(desc, AvbPropertyDescriptor):
            # Remove duplicate property descriptors
            if desc.key in existing:
                avb.descriptors.remove(desc)
            else:
                existing.add(desc.key)

    avb.write()
