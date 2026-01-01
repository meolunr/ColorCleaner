import base64

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Util import Counter


def aes_encrypt(data: bytes):
    key = get_random_bytes(32)
    iv = get_random_bytes(16)
    ctr = Counter.new(128, initial_value=int.from_bytes(iv, 'big'))
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return base64.b64encode(key), base64.b64encode(iv), base64.b64encode(cipher.encrypt(data))


def aes_decrypt(key: bytes, iv: bytes, data: bytes):
    key = base64.b64decode(key)
    iv = base64.b64decode(iv)
    data = base64.b64decode(data)

    ctr = Counter.new(128, initial_value=int.from_bytes(iv, 'big'))
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return cipher.decrypt(data)


def rsa_encrypt(public_key: str, data: bytes):
    public_key = RSA.import_key(base64.b64decode(public_key.encode('utf-8')))
    cipher = PKCS1_OAEP.new(public_key)
    return base64.b64encode(cipher.encrypt(data))
