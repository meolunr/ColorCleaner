import copy
import io
import os
import re
import shutil
import string
import sys
from glob import glob
from pathlib import Path
from zipfile import ZipFile

import config
from build.apkfile import ApkFile
from build.smali import MethodSpecifier
from build.xml import XmlFile
from ccglobal import MISC_DIR, log

_MODIFIED_FLAG = b'CC-Mod'


def modified(file: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not os.path.isfile(file):
                return None

            with ZipFile(file, 'r') as f:
                comment = f.comment
            if comment != _MODIFIED_FLAG:
                func_result = func(*args, **kwargs)

                with ZipFile(file, 'a') as f:
                    f.comment = _MODIFIED_FLAG

                oat = Path(file).parent.joinpath('oat')
                if oat.exists():
                    shutil.rmtree(oat)
                return func_result
            else:
                return None

        return wrapper

    return decorator


def rm_files():
    def ignore_comment(line: str):
        annotation_index = line.find('#')
        if annotation_index >= 0:
            line = line[:annotation_index]
        return line.strip()

    with open(f'{sys.path[0]}/remove-files.txt', 'r', encoding='utf-8') as f:
        for item in map(ignore_comment, f.readlines()):
            if len(item) == 0:
                continue
            if os.path.exists(item):
                log(f'删除文件: {item}')
                if os.path.isdir(item):
                    shutil.rmtree(item)
                else:
                    os.remove(item)
            else:
                log(f'文件不存在: {item}')


def replace_installer():
    log('替换 PUIPackageInstaller')
    shutil.rmtree('system_ext/priv-app/OppoPackageInstaller')

    pui_dir = 'system_ext/priv-app/PUIPackageInstaller'
    os.makedirs(pui_dir)
    shutil.copy(f'{MISC_DIR}/PUIPackageInstaller.apk', pui_dir)


def remove_activity_start_dialog():
    log('禁用关联启动对话框')
    xml = XmlFile('my_stock/etc/extension/com.oplus.oplus-feature.xml')
    root = xml.get_root()
    element = root.find('oplus-feature[@name="oplus.software.activity_start_manager"]')
    root.remove(element)
    xml.commit()


def turn_off_flashlight_with_power_key():
    log('启用电源键关闭手电筒')
    xml = XmlFile('system_ext/etc/permissions/com.oplus.features_config.xml')
    root = xml.get_root()
    element = root.find('oplus-feature[@name="oplus.software.powerkey_disbale_turnoff_torch"]')
    root.remove(element)
    xml.commit()


@modified('system/system/framework/oplus-services.jar')
def patch_oplus_services():
    apk = ApkFile('system/system/framework/oplus-services.jar')
    apk.decode()

    log('禁用 ADB 安装确认')
    smali = apk.open_smali('com/android/server/pm/OplusPackageInstallInterceptManager.smali')
    specifier = MethodSpecifier()
    specifier.name = 'allowInterceptAdbInstallInInstallStage'
    specifier.parameters = 'ILandroid/content/pm/PackageInstaller$SessionParams;Ljava/io/File;Ljava/lang/String;Landroid/content/pm/IPackageInstallObserver2;'
    smali.method_return_boolean(specifier, False)

    log('去除已激活 VPN 通知')
    smali = apk.open_smali('com/android/server/connectivity/VpnExtImpl.smali')
    specifier = MethodSpecifier()
    specifier.name = 'showNotification'
    specifier.parameters = 'Ljava/lang/String;IILjava/lang/String;Landroid/app/PendingIntent;Lcom/android/internal/net/VpnConfig;'
    smali.method_nop(specifier)

    apk.build()
    for file in glob('system/system/framework/**/oplus-services.*', recursive=True):
        if not os.path.samefile(apk.file, file):
            os.remove(file)


@modified('system_ext/priv-app/SystemUI/SystemUI.apk')
def patch_system_ui():
    apk = ApkFile('system_ext/priv-app/SystemUI/SystemUI.apk')
    apk.decode()

    log('禁用控制中心时钟红1')
    smali = apk.open_smali('com/oplus/systemui/common/clock/OplusClockExImpl.smali')
    specifier = MethodSpecifier()
    specifier.name = 'setTextWithRedOneStyle'
    specifier.parameters = 'Landroid/widget/TextView;Ljava/lang/CharSequence;'
    specifier.return_type = 'Z'
    new_body = '''\
.method public setTextWithRedOneStyle(Landroid/widget/TextView;Ljava/lang/CharSequence;)Z
    .locals 0

    invoke-virtual {p1, p2}, Landroid/widget/TextView;->setText(Ljava/lang/CharSequence;)V

    iget-boolean p0, p0, Lcom/oplus/systemui/common/clock/OplusClockExImpl;->mIsDateTimePanel:Z

    return p0
.end method
'''
    smali.method_replace(specifier, new_body)

    smali = apk.open_smali('com/oplus/keyguard/utils/KeyguardUtils$Companion.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getSpannedHourString'
    specifier.parameters = 'Landroid/content/Context;Ljava/lang/String;'
    specifier.return_type = 'Landroid/text/SpannableStringBuilder;'
    new_body = '''\
.method public final getSpannedHourString(Landroid/content/Context;Ljava/lang/String;)Landroid/text/SpannableStringBuilder;
    .locals 0

    new-instance p1, Landroid/text/SpannableStringBuilder;

    invoke-direct {p1, p2}, Landroid/text/SpannableStringBuilder;-><init>(Ljava/lang/CharSequence;)V

    return p1
.end method
'''
    smali.method_replace(specifier, new_body)

    log('去除开发者选项通知')
    smali = apk.open_smali('com/oplus/systemui/statusbar/controller/SystemPromptController.smali')
    specifier = MethodSpecifier()
    specifier.name = 'updateDeveloperMode'
    smali.method_nop(specifier)

    log('去除免打扰模式通知')
    smali = apk.open_smali('com/oplus/systemui/statusbar/notification/helper/DndAlertHelper.smali')
    specifier = MethodSpecifier()
    specifier.name = 'operateNotification'
    specifier.parameters = 'IJZ'
    smali.method_nop(specifier)

    log('禁用 USB 选择弹窗')
    smali = apk.open_smali('com/oplus/systemui/usb/UsbService.smali')
    specifier = MethodSpecifier()
    specifier.name = 'performUsbDialogAction'
    insert = '''\
    const/16 v0, 0x3ea
    
    if-eq p1, v0, :jump_return
    
    const/16 v0, 0x3eb
    
    if-ne p1, v0, :jump_normal
    
    :jump_return
    return-void
    
    :jump_normal
'''
    smali.method_insert_before(specifier, insert)

    apk.build()


@modified('system_ext/app/KeyguardClockBase/KeyguardClockBase.apk')
def disable_lock_screen_red_one():
    log('禁用锁屏时钟红1')
    apk = ApkFile('system_ext/app/KeyguardClockBase/KeyguardClockBase.apk')
    apk.decode()

    smali = apk.open_smali('com/oplus/keyguard/clock/base/widget/CustomizedTextView.smali')
    specifier = MethodSpecifier()
    specifier.name = 'setHourText'
    specifier.parameters = 'Z'
    smali.method_nop(specifier)

    apk.build()


@modified('my_stock/app/Clock/Clock.apk')
def disable_launcher_clock_red_one():
    log('禁用桌面时钟小部件红1')
    apk = ApkFile('my_stock/app/Clock/Clock.apk')
    apk.decode()

    smali = apk.find_smali('"DeviceUtils"', '"not found class:com.oplus.widget.OplusTextClock"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.is_static = True
    specifier.parameters = ''
    specifier.return_type = 'Z'
    specifier.keywords.add('"not found class:com.oplus.widget.OplusTextClock"')
    smali.method_return_boolean(specifier, False)

    apk.build()


@modified('system_ext/priv-app/OplusLauncher/OplusLauncher.apk')
def patch_launcher():
    apk = ApkFile('system_ext/priv-app/OplusLauncher/OplusLauncher.apk')
    apk.decode()

    log('允许最近任务显示内存信息')
    smali = apk.open_smali('com/oplus/quickstep/memory/MemoryInfoManager.smali')
    specifier = MethodSpecifier()
    specifier.name = 'judgeWhetherAllowMemoDisplay'
    new_body = '''\
.method private judgeWhetherAllowMemoDisplay()V
    .locals 1

    const/4 v0, 0x1

    iput-boolean v0, p0, Lcom/oplus/quickstep/memory/MemoryInfoManager;->mAllowMemoryInfoDisplay:Z
    
    invoke-direct {p0, v0}, Lcom/oplus/quickstep/memory/MemoryInfoManager;->saveAllowMemoryInfoDisplay(Z)Z

    return-void
.end method
'''
    smali.method_replace(specifier, new_body)

    log('禁用最近任务自动聚焦到下一个应用')
    smali = apk.open_smali('com/android/common/util/AppFeatureUtils.smali')
    specifier = MethodSpecifier()
    specifier.name = 'isSupportAutoFocusToNextPageInOverviewState'
    specifier.parameters = 'Z'
    smali.method_return_boolean(specifier, False)

    log('桌面主页设置为第二页')
    smali = apk.open_smali('com/android/launcher3/Workspace.smali')
    specifier = MethodSpecifier()
    specifier.name = 'initWorkspace'

    old_body = smali.find_method(specifier)
    pattern = r'''
    invoke-static {}, Lcom/android/launcher/mode/LauncherModeManager;->getInstance\(\)Lcom/android/launcher/mode/LauncherModeManager;
(?:.|\n)*?
    move-result (?:[v|p]\d+)

    (sput ([v|p]\d+), Lcom/android/launcher3/Workspace;->DEFAULT_PAGE:I)
'''
    repl = r'''
    const/4 \g<2>, 0x1
    
    \g<1>
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('system_ext/app/OplusCommercialEngineerMode/OplusCommercialEngineerMode.apk')
def show_touchscreen_panel_info():
    log('显示工程模式中的屏生产信息')
    apk = ApkFile('system_ext/app/OplusCommercialEngineerMode/OplusCommercialEngineerMode.apk')
    apk.refactor()
    apk.decode(False)

    xml = apk.open_xml('xml/as_multimedia_test.xml')
    root = xml.get_root()
    attr_title = xml.make_attr_key('android:title')
    for index, element in enumerate(root):
        if element.tag == 'androidx.preference.Preference' and element.get(attr_title) == '@string/lcd_brightness':
            new_element = copy.deepcopy(element)
            new_element.set(attr_title, '@string/lcd_info_title')
            new_element.set(xml.make_attr_key('android:key'), 'lcd_info')
            new_element.find('intent').set(xml.make_attr_key('android:targetClass'), 'com.oplus.engineermode.display.lcd.modeltest.LcdInfoActivity')
            root.insert(index + 1, new_element)
    xml.commit()

    apk.build()


@modified('system_ext/priv-app/WirelessSettings/WirelessSettings.apk')
def show_netmask_and_gateway():
    log('显示 WLAN 设置中的子网掩码和网关')
    apk = ApkFile('system_ext/priv-app/WirelessSettings/WirelessSettings.apk')
    apk.decode()
    apk.add_smali(f'{MISC_DIR}/smali/WirelessSettings.smali', 'com/meolunr/colorcleaner/CcInjector.smali')

    smali = apk.open_smali('com/oplus/wirelesssettings/wifi/detail2/WifiAddressController.smali')
    old_body = smali.find_constructor('Landroid/content/Context;Lcom/android/wifitrackerlib/WifiEntry;')
    context_field = re.search(r'iput-object p1, p0, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->(\S+?):Landroid/content/Context;', old_body).group(1)

    specifier = MethodSpecifier()
    specifier.name = 'displayPreference'
    specifier.parameters = 'Landroidx/preference/PreferenceScreen;'
    old_body = smali.find_method(specifier)
    pattern1 = r'''
    const-string (?:[v|p]\d+), "{key}"
'''
    pattern2 = r'''
    invoke-virtual {p1, (?:[v|p]\d+)}, Landroidx/preference/PreferenceGroup;->findPreference\(Ljava/lang/CharSequence;\)Landroidx/preference/Preference;

    move-result-object (?:[v|p]\d+)

    iput-object (?:[v|p]\d+), p0, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->(\S+?):Landroidx/preference/Preference;
'''
    ip_preference_field = re.search(f'{pattern1.format(key='current_ip_address')}{pattern2}', old_body).group(1)
    ipv4_preference_field = re.search(f'{pattern1.format(key='current_ipv4_address')}{pattern2}', old_body).group(1)
    ipv6_preference_field = re.search(f'{pattern1.format(key='current_ipv6_address')}{pattern2}', old_body).group(1)

    specifier = MethodSpecifier()
    specifier.parameters = ''
    specifier.return_type = 'Z'
    specifier.keywords.add('"WifiAddressController"')
    specifier.keywords.add('"updateIpInfo:')
    update_ip_info_method = re.search(r'\.method public final (\S+?)\(\)Z', smali.find_method(specifier)).group(1)

    specifier = MethodSpecifier()
    specifier.parameters = ''
    specifier.return_type = 'Z'
    specifier.keywords.add(f'Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->{update_ip_info_method}()Z')

    old_body = smali.find_method(specifier)
    pattern = f'''\
    .locals 1
((?:.|\\n)*?
    invoke-virtual {{p0}}, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->\\S+?\\(\\)Z
)
    move-result p0
((?:.|\\n)*?
    invoke-virtual {{p0}}, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->{update_ip_info_method}\\(\\)Z
)
    move-result p0
((?:.|\\n)*?)
    return p0
'''
    repl = f'''\
    .locals 4
\\g<1>
    move-result v0
\\g<2>
    move-result v0

    if-eqz v0, :jump
    
    iget-object v1, p0, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->{context_field}:Landroid/content/Context;
    
    iget-object v2, p0, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->{ip_preference_field}:Landroidx/preference/Preference;
    
    iget-object v3, p0, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->{ipv4_preference_field}:Landroidx/preference/Preference;

    iget-object p0, p0, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->{ipv6_preference_field}:Landroidx/preference/Preference;

    invoke-static {{v1, v2, v3, p0}}, Lcom/meolunr/colorcleaner/CcInjector;->\
showNetmaskAndGateway(Landroid/content/Context;Landroidx/preference/Preference;Landroidx/preference/Preference;Landroidx/preference/Preference;)V

    :jump\\g<3>
    return v0
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('system_ext/priv-app/Settings/Settings.apk')
def patch_settings():
    apk = ApkFile('system_ext/priv-app/Settings/Settings.apk')
    apk.decode()
    apk.add_smali(f'{MISC_DIR}/smali/Settings.smali', 'com/meolunr/colorcleaner/CcInjector.smali')

    log('禁用设备名称敏感词检查')
    smali = apk.open_smali('com/oplus/settings/feature/deviceinfo/aboutphone/PhoneNameVerifyUtil.smali')
    specifier = MethodSpecifier()
    specifier.name = 'activeNeedServerVerify'
    specifier.parameters = 'Ljava/lang/String;'
    smali.method_return_boolean(specifier, False)

    log('显示应用详情中的包名和版本代码')
    smali = apk.open_smali('com/oplus/settings/feature/appmanager/AppInfoFeature.smali')
    specifier = MethodSpecifier()
    specifier.name = 'setAppLabelAndIcon'
    specifier.parameters = 'Lcom/android/settings/applications/appinfo/AppButtonsPreferenceController;'

    old_body = smali.find_method(specifier)
    pattern = r'''
    invoke-virtual {p0, ([v|p]\d+)}, Lcom/oplus/settings/feature/appmanager/AppInfoFeature;->getVersionName\(Landroid/content/pm/PackageInfo;\)Ljava/lang/CharSequence;
(?:.|\n)*?
    invoke-virtual {p1, (?:[v|p]\d+), (?:[v|p]\d+)}, Landroidx/fragment/app/Fragment;->getString\(I\[Ljava/lang/Object;\)Ljava/lang/String;

    move-result-object (?:[v|p]\d+)

    invoke-virtual {([v|p]\d+), (?:[v|p]\d+)}, Landroid/widget/TextView;->setText\(Ljava/lang/CharSequence;\)V
'''
    repl = r'''
    invoke-static {\g<2>, \g<1>}, Lcom/meolunr/colorcleaner/CcInjector;->setPackageAndVersion(Landroid/widget/TextView;Landroid/content/pm/PackageInfo;)V
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('system_ext/priv-app/TeleService/TeleService.apk')
def patch_tele_service():
    apk = ApkFile('system_ext/priv-app/TeleService/TeleService.apk')
    apk.decode()

    log('显示首选网络类型')
    smali = apk.find_smali('"SIMS_OplusSimInfoActivity"', '"changeNetworkModeConfig type:"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.parameters = 'ILjava/lang/String;Z'
    specifier.return_type = 'V'
    specifier.keywords.add('"changeNetworkModeConfig type:"')
    insert = '''\
    const/4 v0, 0x1

    if-ne p1, v0, :jump

    const/4 p3, 0x1

    :jump
'''
    smali.method_insert_before(specifier, insert)

    log('去除移动网络中的流量卡广告')
    smali = apk.find_smali('"SIMS_TrafficCardUtils"', '"clearHighDataSimCardConfiguration"').pop()
    specifier = MethodSpecifier()
    specifier.name = 'run'
    specifier.parameters = ''

    old_body = smali.find_method(specifier)
    pattern = r'''
    sget-object (?:[v|p]\d+), Lcom/android/phone/ConfigurationConstants;->INSTANCE:Lcom/android/phone/ConfigurationConstants;

    invoke-virtual {(?:[v|p]\d+)}, Lcom/android/phone/ConfigurationConstants;->getTRAFFIC_CARD_PACKAGE_NAME\(\)Ljava/lang/String;

    move-result-object (?:[v|p]\d+)

    const-string (?:[v|p]\d+), "basewallet_traffic_card_support"

    const-string (?:[v|p]\d+), "true"

    invoke-static {(?:(?:[v|p]\d+), ){3}(?:[v|p]\d+)}, Lcom/android/phone/oplus/share/.+?;->.+?\(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;\)Z

    move-result ([v|p]\d+)
'''
    repl = '''
const/4 \\g<1>, 0x0
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('system_ext/priv-app/TrafficMonitor/TrafficMonitor.apk')
def remove_traffic_monitor_ads():
    log('去除流量管理中的流量卡广告')
    apk = ApkFile('system_ext/priv-app/TrafficMonitor/TrafficMonitor.apk')
    apk.decode()

    smali = apk.find_smali('"datausage_TrafficCardController"', '"updateHighDataSimCardConfiguration"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.is_final = True
    specifier.parameters = 'Landroid/content/Context;I'
    specifier.return_type = 'V'
    specifier.keywords.add('"updateHighDataSimCardConfiguration"')

    old_body = smali.find_method(specifier)
    pattern = r'''
    const-string (?:[v|p]\d+), "basewallet_traffic_card_support"

    const-string (?:[v|p]\d+), "true"

    invoke-static {p1(?:, [v|p]\d+){3}}, L.+?;->.+?\(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;\)Z

    move-result ([v|p]\d+)
'''
    repl = '''
    const/4 \\g<1>, 0x0
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    smali = apk.find_smali('"datausage_SysFeatureUtils"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.is_final = True
    specifier.parameters = ''
    specifier.return_type = 'Ljava/lang/String;'
    for keyword in ('"com.oplus.trafficmonitor.wallet_uri"', '"com.oplus.trafficmonitor.wallet_H5_uri"'):
        specifier.keywords.clear()
        specifier.keywords.add(keyword)
        smali.method_return_null(specifier)

    apk.build()


@modified('system_ext/app/NotificationCenter/NotificationCenter.apk')
def show_icon_for_silent_notification():
    log('允许显示静默通知的图标')
    apk = ApkFile('system_ext/app/NotificationCenter/NotificationCenter.apk')
    apk.decode()

    smali = apk.open_smali('com/oplus/notificationmanager/fragments/main/MoreSettingFragment.smali')
    specifier = MethodSpecifier()
    specifier.name = 'onCreateView'
    specifier.parameters = 'Landroid/view/LayoutInflater;Landroid/view/ViewGroup;Landroid/os/Bundle;'

    old_body = smali.find_method(specifier)
    pattern = '''\
    const-string (?:[v|p]\\d+), "hide_silence_notification_icon_enable"

    invoke-static {}, Lcom/oplus/notificationmanager/config/BaseFeatureOption;->isExpVersion\\(\\)Z

    move-result (?:[v|p]\\d+)

    invoke-static {(?:(?:[v|p]\\d+), ){3}(?:[v|p]\\d+)}, Lcom/oplus/notificationmanager/view/PerferenceExKt;->\
initPreference\\(Landroidx/preference/PreferenceFragmentCompat;Ljava/lang/String;Ljava/lang/Class;Z\\)Landroidx/preference/Preference;
'''
    new_body = re.sub(pattern, '', old_body)
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('my_stock/app/MCS/MCS.apk')
def remove_system_notification_ads():
    log('去除系统通知广告')
    apk = ApkFile('my_stock/app/MCS/MCS.apk')
    apk.decode()

    smali = apk.find_smali('"excellent recommendation"', r'"\u7cbe\u5f69\u63a8\u8350"').pop()
    specifier = MethodSpecifier()
    specifier.is_static = True
    specifier.parameters = 'Landroid/content/Context;Z'
    specifier.keywords.add('"excellent recommendation"')
    specifier.keywords.add(r'"\u7cbe\u5f69\u63a8\u8350"')
    smali.method_nop(specifier)

    apk.build()


@modified('my_stock/app/Calendar/Calendar.apk')
def remove_calendar_ads():
    log('去除日历广告')
    apk = ApkFile('my_stock/app/Calendar/Calendar.apk')
    apk.decode()

    smali = apk.open_smali('com/android/calendar/module/subscription/almanac/adapter/AlmanacPagesAdapter.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getItemViewType'
    specifier.parameters = 'I'
    new_body = '''\
.method public getItemViewType(I)I
    .locals 0

    invoke-super {p0, p1}, Landroidx/recyclerview/widget/RecyclerView$Adapter;->getItemViewType(I)I

    move-result p0

    return p0
.end method
'''
    smali.method_replace(specifier, new_body)

    smali = apk.open_smali('com/coloros/calendar/app/cloudconfig/CloudOperate.smali')
    specifier = MethodSpecifier()
    specifier.name = 'loadUnSupportAdPhoneConfig'
    specifier.parameters = ''
    smali.method_nop(specifier)

    smali = apk.open_smali('com/coloros/calendar/app/cloudconfig/utils/UnSupportAdPhoneHelp.smali')
    specifier = MethodSpecifier()
    specifier.name = 'isUnsupportedPhone'
    specifier.parameters = 'Ljava/lang/String;'
    smali.method_return_boolean(specifier, True)

    apk.build()


def patch_services():
    log('去除系统签名检查')
    apk = ApkFile('system/system/framework/services.jar')
    apk.decode()

    specifier = MethodSpecifier()
    specifier.keywords.add('getMinimumSignatureSchemeVersionForTargetSdk')
    pattern = '''\
    invoke-static .+?, Landroid/util/apk/ApkSignatureVerifier;->getMinimumSignatureSchemeVersionForTargetSdk\\(I\\)I

    move-result ([v|p]\\d)
'''
    repl = '''\
    const/4 \\g<1>, 0x0
'''
    for smali in apk.find_smali('getMinimumSignatureSchemeVersionForTargetSdk'):
        old_body = smali.find_method(specifier)
        new_body = re.sub(pattern, repl, old_body)
        smali.method_replace(old_body, new_body)

    # Remove the black screen when capturing display
    smali = apk.open_smali('com/android/server/wm/WindowState.smali')
    specifier = MethodSpecifier()
    specifier.name = 'isSecureLocked'
    smali.method_return_boolean(specifier, False)

    apk.build()
    for file in glob('system/system/framework/oat/arm64/services.*'):
        os.remove(file)


def patch_miui_services():
    apk = ApkFile('system_ext/framework/miui-services.jar')
    apk.decode()

    log('防止主题恢复')
    smali = apk.open_smali('com/android/server/am/ActivityManagerServiceImpl.smali')
    specifier = MethodSpecifier()
    specifier.name = 'finishBooting'
    specifier.parameters = ''
    old_body = smali.find_method(specifier)
    pattern = '''\
    invoke-static {.+?}, Lmiui/drm/DrmBroadcast;->getInstance\\(Landroid/content/Context;\\)Lmiui/drm/DrmBroadcast;

    move-result-object .+?

    invoke-virtual {.+?}, Lmiui/drm/DrmBroadcast;->broadcast\\(\\)V
'''
    new_body = re.sub(pattern, '', old_body)
    smali.method_replace(old_body, new_body)

    log('允许对任意应用截屏')
    smali = apk.open_smali('com/android/server/wm/WindowManagerServiceImpl.smali')
    specifier = MethodSpecifier()
    specifier.name = 'notAllowCaptureDisplay'
    specifier.parameters = 'Lcom/android/server/wm/RootWindowContainer;I'
    smali.method_return_boolean(specifier, False)

    apk.build()
    for file in glob('system_ext/framework/**/miui-services.*', recursive=True):
        if not os.path.samefile(apk.file, file):
            os.remove(file)


@modified('product/app/MIUIThemeManager/MIUIThemeManager.apk')
def patch_theme_manager():
    apk = ApkFile('product/app/MIUIThemeManager/MIUIThemeManager.apk')
    apk.decode()

    log('去除主题商店广告')
    smali = apk.open_smali('com/android/thememanager/basemodule/ad/model/AdInfoResponse.smali')
    specifier = MethodSpecifier()
    specifier.name = 'isAdValid'
    smali.method_return_boolean(specifier, False)

    # Filter advertising elements
    smali = apk.find_smali('"DetailRecommendFactory.java"').pop()
    specifier = MethodSpecifier()
    specifier.parameters = 'Lcom/android/thememanager/router/recommend/entity/UICard;'
    specifier.return_type = 'Ljava/util/List;'

    old_body = smali.find_method(specifier)
    pattern = '''\
    :goto_(\\d)
    invoke-interface {.+?}, Ljava/util/Iterator;->hasNext\\(\\)Z
'''
    match = re.search(pattern, old_body)
    goto = match.group(1)
    pattern = '''\
    check-cast ([v|p]\\d), Lcom/android/thememanager/router/recommend/entity/UIImageWithLink;
(?:.|\n)*?
    const/4 ([v|p]\\d), 0x1
'''
    repl = f'''\
    check-cast \\g<1>, Lcom/android/thememanager/router/recommend/entity/UIImageWithLink;

    iget-object \\g<2>, \\g<1>, Lcom/android/thememanager/router/recommend/entity/UIImageWithLink;->adInfo:Lcom/android/thememanager/basemodule/ad/model/AdInfoResponse;

    if-nez \\g<2>, :goto_{goto}

    const/4 \\g<2>, 0x1
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    log('破解主题免费')
    smali = apk.open_smali('com/android/thememanager/detail/theme/model/OnlineResourceDetail.smali')
    specifier = MethodSpecifier()
    specifier.name = 'toResource'
    specifier.return_type = 'Lcom/android/thememanager/basemodule/resource/model/Resource;'

    old_body = smali.find_method(specifier)
    pattern = '''\
    return-object ([v|p]\\d)
'''
    match = re.search(pattern, old_body)
    register1 = match.group(1)
    num = int(register1[1:]) - 1
    if num < 0:
        num += 2
    register2 = f'{register1[:1]}{num}'

    repl = f'''\
    const/4 {register2}, 0x1

    iput-boolean {register2}, p0, Lcom/android/thememanager/detail/theme/model/OnlineResourceDetail;->bought:Z

    return-object {register1}
'''
    new_body = old_body.replace(match.group(0), repl)
    smali.method_replace(old_body, new_body)

    smali = apk.open_smali('com/android/thememanager/basemodule/views/DiscountPriceView.smali')
    specifier = MethodSpecifier()
    specifier.name = 'setPrice'
    specifier.parameters = 'II'

    old_body = smali.find_method(specifier)
    lines = old_body.splitlines()
    lines.insert(12, 'const/4 p1, 0x0')
    lines.insert(13, 'const/4 p2, 0x0')
    smali.method_replace(old_body, '\n'.join(lines))

    smali = apk.find_smali('"DrmService.java"', '"theme"', '"check rights isLegal: "').pop()
    specifier = MethodSpecifier()
    specifier.parameters = 'Lcom/android/thememanager/basemodule/resource/model/Resource;'
    specifier.return_type = 'Lmiui/drm/DrmManager$DrmResult;'

    old_body = smali.find_method(specifier)
    lines = old_body.splitlines()
    new_body = f'''\
{lines[0]}
    .locals 0

    sget-object p0, Lmiui/drm/DrmManager$DrmResult;->DRM_SUCCESS:Lmiui/drm/DrmManager$DrmResult;

    return-object p0
.end method
'''
    smali.method_replace(old_body, new_body)

    smali = apk.open_smali('com/miui/maml/widget/edit/MamlutilKt.smali')
    specifier = MethodSpecifier()
    specifier.name = 'themeManagerSupportPaidWidget'
    specifier.parameters = 'Landroid/content/Context;'
    smali.method_return_boolean(specifier, False)

    apk.build()


@modified('product/priv-app/MiuiMms/MiuiMms.apk')
def remove_mms_ads():
    apk = ApkFile('product/priv-app/MiuiMms/MiuiMms.apk')
    apk.decode()

    log('去除短信输入框广告')
    smali = apk.open_smali('com/miui/smsextra/ui/BottomMenu.smali')
    specifier = MethodSpecifier()
    specifier.name = 'allowMenuMode'
    specifier.return_type = 'Z'
    smali.method_return_boolean(specifier, False)

    log('去除短信下方广告')
    specifier = MethodSpecifier()
    specifier.name = 'setHideButton'
    specifier.is_abstract = False
    pattern = '''\
    iput-boolean ([v|p]\\d), p0, L.+?;->.+?:Z
'''
    repl = '''\
    const/4 \\g<1>, 0x1

\\g<0>'''
    for smali in apk.find_smali('final setHideButton'):
        old_body = smali.find_method(specifier)
        new_body = re.sub(pattern, repl, old_body)
        smali.method_replace(old_body, new_body)

    apk.build()


@modified('product/priv-app/MIUISecurityCenter/MIUISecurityCenter.apk')
def patch_security_center():
    apk = ApkFile('product/priv-app/MIUISecurityCenter/MIUISecurityCenter.apk')
    apk.decode()

    log('显示电池健康度')
    smali = apk.find_smali('.class Lcom/miui/powercenter/nightcharge/ChargeProtectFragment$', '.super Landroid/os/Handler;').pop()
    specifier = MethodSpecifier()
    specifier.name = 'handleMessage'
    specifier.parameters = 'Landroid/os/Message;'
    old_body = smali.find_method(specifier)

    utils_smali = apk.find_smali('"BatteryHealthUtils"').pop()
    utils_type_signature = utils_smali.get_type_signature()

    specifier = MethodSpecifier()
    specifier.keywords.add('"persist.vendor.smart.battMntor"')
    method_signature_1 = utils_smali.find_method(specifier).splitlines()[0].split(' ')[-1]
    specifier.keywords.clear()
    specifier.keywords.add('"key_get_battery_health_value"')
    method_signature_2 = utils_smali.find_method(specifier).splitlines()[0].split(' ')[-1]
    specifier.keywords.clear()
    specifier.keywords.add('"getBatterySoh: "')
    method_signature_3 = utils_smali.find_method(specifier).splitlines()[0].split(' ')[-1]

    pattern = f'''\
    invoke-static {{}}, {utils_type_signature}->{re.escape(method_signature_1)}

    move-result .+?

    if-eqz .+?, :cond_\\d

    invoke-static {{}}, {utils_type_signature}->{re.escape(method_signature_2)}

    move-result ([v|p]\\d)
'''
    repl = f'''\
    invoke-static {{}}, {utils_type_signature}->{method_signature_3}

    move-result-object \\g<1>

    :try_start_114
    invoke-static {{\\g<1>}}, Ljava/lang/Integer;->parseInt(Ljava/lang/String;)I

    move-result \\g<1>
    :try_end_514
    .catch Ljava/lang/NumberFormatException; {{:try_start_114 .. :try_end_514}} :catch_1919

    goto :goto_810

    :catch_1919
    move-exception \\g<1>

    const/4 \\g<1>, -0x1

    :goto_810
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    log('显示电池温度')
    smali = apk.open_smali('com/miui/powercenter/nightcharge/ChargeProtectFragment.smali')
    specifier = MethodSpecifier()
    specifier.parameters = 'Landroid/content/Context;'
    specifier.return_type = 'Ljava/lang/String;'
    specifier.is_static = True
    specifier.keywords.add('-0x80000000')
    old_body = smali.find_method(specifier)

    pattern = f'''\
    invoke-static {{p0}}, L.+?;->.+?\\(Landroid/content/Context;\\)I

    move-result ([v|p]\\d)

    invoke-static {{p0}}, L.+?;->.+?\\(Landroid/content/Context;\\)I

    move-result ([v|p]\\d)

    const/high16 .+?, -0x80000000
(?:.|\\n)*?
    const/4 ([v|p]\\d), 0x5

    if-le .+?, \\3, :cond_(\\d)

    :cond_\\d
    move \\1, \\2

    :cond_\\4
'''
    match = re.search(pattern, old_body)
    register1 = match.group(1)
    register2 = match.group(2)
    cond = match.group(4)

    pattern = f'''\
    :cond_{cond}
(?:.|\\n)*?
.end method'''
    repl = f'''\
    :cond_{cond}
    new-instance {register2}, Ljava/lang/StringBuilder;

    invoke-direct {{{register2}}}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {{{register2}, {register1}}}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    const-string {register1}, "℃"

    invoke-virtual {{{register2}, {register1}}}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {{{register2}}}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object {register1}

    return-object {register1}
.end method'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    log('手机管家 100 分')
    # Lock 100 score
    smali = apk.open_smali('com/miui/securityscan/scanner/ScoreManager.smali')
    specifier = MethodSpecifier()
    specifier.return_type = 'I'
    specifier.keywords.add('getMinusPredictScore')

    old_body = smali.find_method(specifier)
    lines = old_body.splitlines()
    new_body = f'''\
{lines[0]}
    .locals 0

    const/16 p0, 0x0

    return p0
.end method
'''
    smali.method_replace(old_body, new_body)

    # Disable click events
    smali = apk.open_smali('com/miui/securityscan/ui/main/MainContentFrame.smali')
    specifier = MethodSpecifier()
    specifier.name = 'onClick'
    specifier.parameters = 'Landroid/view/View;'
    smali.method_nop(specifier)

    log('去除危险操作倒计时确认')
    smali = apk.open_smali('com/miui/permcenter/privacymanager/model/InterceptBaseActivity.smali')
    specifier = MethodSpecifier()
    specifier.name = 'onCreate'
    specifier.parameters = 'Landroid/os/Bundle;'

    old_body = smali.find_method(specifier)
    lines = old_body.splitlines()
    locals_line = list(lines[1])
    if int(locals_line[-1]) < 2:
        locals_line[-1] = '2'
    lines[1] = ''.join(locals_line)
    new_body = '\n'.join(lines)

    pattern = '''\
    invoke-super {p0, p1}, Lmiuix/appcompat/app/AppCompatActivity;->onCreate\\(Landroid/os/Bundle;\\)V
'''
    repl = '''\\g<0>
    if-nez p1, :cond_114514

    new-instance v0, Landroid/os/Bundle;

    invoke-direct {v0}, Landroid/os/Bundle;-><init>()V

    move-object p1, v0

    :cond_114514

    const-string v0, "KET_STEP_COUNT"

    const/4 v1, 0x0

    invoke-virtual {p1, v0, v1}, Landroid/os/Bundle;->putInt(Ljava/lang/String;I)V

    const-string v0, "KEY_ALLOW_ENABLE"

    const/4 v1, 0x1

    invoke-virtual {p1, v0, v1}, Landroid/os/Bundle;->putBoolean(Ljava/lang/String;Z)V
'''
    new_body = re.sub(pattern, repl, new_body)
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('product/app/MIUISuperMarket/MIUISuperMarket.apk')
def not_update_modified_app():
    log('不检查修改过的系统应用更新')
    apk = ApkFile('product/app/MIUISuperMarket/MIUISuperMarket.apk')
    apk.decode()

    smali = apk.open_smali('com/xiaomi/market/data/LocalAppManager.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getUpdateInfoFromServer'
    old_body = smali.find_method(specifier)
    pattern = '''\
    invoke-direct/range {.+?}, Lcom/xiaomi/market/data/LocalAppManager;->loadInvalidSystemPackageList\\(\\)Ljava/util/List;

    move-result-object ([v|p]\\d+?)
'''
    repl = '''\\g<0>
    invoke-static {\\g<1>}, Lcom/xiaomi/market/data/CcInjector;->addModifiedPackages(Ljava/util/List;)V
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    # If the cccm (ColorCleaner Check Modified) file exists in the internal storage root directory, ignore adding packages
    smali.add_affiliated_smali(f'{MISC_DIR}/smali/IgnoreAppUpdate.smali', 'CcInjector.smali')
    smali = apk.open_smali('com/xiaomi/market/data/CcInjector.smali')
    specifier.name = 'addModifiedPackages'
    old_body = smali.find_method(specifier)
    output = io.StringIO()
    for package in config.MODIFY_PACKAGE:
        output.write(f'    const-string v1, "{package}"\n\n')
        output.write('    invoke-interface {p0, v1}, Ljava/util/List;->add(Ljava/lang/Object;)Z\n\n')
    new_body = string.Template(old_body).safe_substitute(var_modify_package=output.getvalue())
    smali.method_replace(old_body, new_body)

    apk.build()


def run_on_rom():
    rm_files()
    replace_installer()
    remove_activity_start_dialog()
    turn_off_flashlight_with_power_key()
    patch_oplus_services()
    patch_system_ui()
    patch_launcher()
    disable_lock_screen_red_one()
    disable_launcher_clock_red_one()
    show_touchscreen_panel_info()
    show_netmask_and_gateway()
    patch_settings()
    patch_tele_service()
    remove_traffic_monitor_ads()
    show_icon_for_silent_notification()
    remove_system_notification_ads()
    remove_calendar_ads()


def run_on_module():
    pass
