SUPER_SIZE = 15354134528
SUPER_PARTITIONS = ('system', 'system_ext', 'system_dlkm', 'product', 'vendor', 'vendor_dlkm', 'odm',
                    'my_bigball', 'my_carrier', 'my_company', 'my_engineering', 'my_heytap', 'my_manifest', 'my_preload', 'my_product', 'my_region', 'my_stock')
UNPACK_PARTITIONS = ('boot', 'system', 'system_ext', 'product', 'vendor', 'my_manifest', 'my_product', 'my_stock')
MODIFY_PACKAGE = (
    'com.android.systemui',
    'com.oplus.keyguard.clock.base',
    'com.coloros.alarmclock',
    'com.oplus.engineermode',
    'com.android.settings',
    'com.oplus.wirelesssettings',
    'com.oplus.notificationmanager',
    'com.heytap.mcs',
    'com.coloros.calendar'
)
MODIFY_DELETABLE_APK = (
    'my_stock/del-app/Clock/Clock.apk',
    'my_stock/del-app/Calendar/Calendar.apk'
)

device: str
version: str
sdk: int
kmi: str
