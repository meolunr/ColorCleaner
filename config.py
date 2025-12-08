SUPER_SIZE = 15354134528
SUPER_PARTITIONS = ('system', 'system_ext', 'system_dlkm', 'product', 'vendor', 'vendor_dlkm', 'odm',
                    'my_bigball', 'my_carrier', 'my_company', 'my_engineering', 'my_heytap', 'my_manifest', 'my_preload', 'my_product', 'my_region', 'my_stock')
MODIFY_PACKAGE = (
    'com.miui.packageinstaller',
    'com.android.thememanager',
    'com.android.systemui',
    'com.android.mms',
    'com.android.phone',
    'com.miui.securitycenter',
    'com.lbe.security.miui',
    'com.xiaomi.trustservice',
    'com.xiaomi.market'
)
MODIFY_DELETABLE_APK = (
    'my_stock/del-app/Clock/Clock.apk',
    'my_stock/del-app/Calendar/Calendar.apk'
)

unpack_partitions = {'system', 'system_ext', 'product', 'vendor', 'my_manifest', 'my_product', 'my_stock'}
device: str
version: str
sdk: int
