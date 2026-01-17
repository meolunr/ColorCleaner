import os

import config


def local_real_path(device_path: str):
    if device_path.startswith('/system/'):
        return f'system{device_path}'
    elif device_path.startswith('/product/') and not os.path.exists(device_path[1:]):
        my_partitions = {x for x in config.UNPACK_PARTITIONS if x.startswith('my_')}
        my_partitions.add('my_product/product_overlay')
        for partition in my_partitions:
            path = f'{partition}{device_path[8:]}'
            if os.path.exists(path):
                return path
    return device_path[1:]
