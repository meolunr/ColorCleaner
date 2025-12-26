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
    log('替换 PUI 软件包安装程序')
    shutil.rmtree('system_ext/priv-app/OppoPackageInstaller')

    pui_dir = 'system_ext/priv-app/PUIPackageInstaller'
    os.makedirs(pui_dir)
    shutil.copy(f'{MISC_DIR}/PUIPackageInstaller.apk', pui_dir)


def disable_activity_start_dialog():
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
    move-result [v|p]\d+

    (sput ([v|p]\d+), Lcom/android/launcher3/Workspace;->DEFAULT_PAGE:I)
'''
    repl = r'''
    const/4 \g<2>, 0x1

    \g<1>
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('my_stock/app/KeKeThemeSpace.apk')
def patch_theme_store():
    apk = ApkFile('my_stock/app/KeKeThemeSpace.apk')
    apk.decode()

    log('去除主题商店广告')
    # Remove splash ads
    smali = apk.find_smali('"s-1"', '"getSplashScreen finish splashDto is null"', package='com/nearme/themespace/ad/self').pop()
    specifier = MethodSpecifier()
    specifier.parameters = 'Lcom/oppo/cdo/card/theme/dto/SplashDto;Landroid/os/Handler;'
    specifier.return_type = 'V'
    specifier.keywords.add('"s-1"')
    specifier.keywords.add('"getSplashScreen finish splashDto is null"')

    old_body = smali.find_method(specifier)
    pattern = '''\
(\\.method public \\S+\\(Lcom/oppo/cdo/card/theme/dto/SplashDto;Landroid/os/Handler;\\)V)
(?:.|\n)*?
    iget-object (?:[v|p]\\d+, ){2}(Lcom/nearme/themespace/ad/self/SelfSplashAdManager\\S+;->\\S+:Lcom/nearme/themespace/ad/self/SelfSplashAdManager;)
(?:.|\n)*?
    const-string(?:/jumbo)? [v|p]\\d+, "s-1"
(?:.|\n)*?
    const-string [v|p]\\d+, "getSplashScreen finish splashDto is null"
(?:.|\n)*?
    invoke-static {(?:[v|p]\\d+, ){3}[v|p]\\d+}, (Lcom/nearme/themespace/ad/self/SelfSplashAdManager;->\\S+\\(Lcom/nearme/themespace/ad/self/SelfSplashAdManager;Ljava/lang/String;Ljava/lang/String;Z\\)V)
'''
    match = re.search(pattern, old_body)
    new_body = f'''\
{match.group(1)}
    .locals 3

    move-object/from16 v0, p0
    
    iget-object v0, v0, {match.group(2)}

    const-string v1, ""
    
    const/4 v2, 0x1
    
    invoke-static {{v0, v1, v1, v2}}, {match.group(3)}

    return-void
.end method
'''
    smali.method_replace(old_body, new_body)

    # Remove theme preview ads
    smali = apk.open_smali('com/oppo/cdo/theme/domain/dto/response/HorizontalDto.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getCode'
    smali.method_return_int(specifier, 0)

    log('破解主题免费')
    smali = apk.open_smali('com/oppo/cdo/card/theme/dto/vip/VipUserDto.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getVipStatus'
    smali.method_return_int(specifier, 1)

    specifier = MethodSpecifier()
    specifier.name = 'getVipDays'
    smali.method_return_int(specifier, 999)

    smali = apk.open_smali('com/oppo/cdo/theme/domain/dto/response/PublishProductItemDto.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getIsVipAvailable'
    smali.method_return_int(specifier, 1)

    log('禁用主题自动恢复')
    smali = apk.open_smali('com/nearme/themespace/trial/ThemeTrialExpireReceiver.smali')
    specifier = MethodSpecifier()
    specifier.name = 'onReceive'
    specifier.parameters = 'Landroid/content/Context;Landroid/content/Intent;'
    smali.method_return_null(specifier)

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
    context_field = re.search(r'iput-object p1, p0, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->(\S+):Landroid/content/Context;', old_body).group(1)

    specifier = MethodSpecifier()
    specifier.name = 'displayPreference'
    specifier.parameters = 'Landroidx/preference/PreferenceScreen;'
    old_body = smali.find_method(specifier)
    pattern1 = r'''
    const-string [v|p]\d+, "{key}"
'''
    pattern2 = r'''
    invoke-virtual {p1, [v|p]\d+}, Landroidx/preference/PreferenceGroup;->findPreference\(Ljava/lang/CharSequence;\)Landroidx/preference/Preference;

    move-result-object [v|p]\d+

    iput-object [v|p]\d+, p0, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->(\S+):Landroidx/preference/Preference;
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
    invoke-virtual {{p0}}, Lcom/oplus/wirelesssettings/wifi/detail2/WifiAddressController;->\\S+\\(\\)Z
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
    invoke-virtual {p1, [v|p]\d+, [v|p]\d+}, Landroidx/fragment/app/Fragment;->getString\(I\[Ljava/lang/Object;\)Ljava/lang/String;

    move-result-object [v|p]\d+

    invoke-virtual {([v|p]\d+), [v|p]\d+}, Landroid/widget/TextView;->setText\(Ljava/lang/CharSequence;\)V
'''
    repl = r'''
    invoke-static {\g<2>, \g<1>}, Lcom/meolunr/colorcleaner/CcInjector;->setPackageAndVersion(Landroid/widget/TextView;Landroid/content/pm/PackageInfo;)V
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('my_stock/priv-app/PhoneManager/PhoneManager.apk')
def patch_phone_manager():
    apk = ApkFile('my_stock/priv-app/PhoneManager/PhoneManager.apk')
    apk.decode()

    log('去除手机管家广告')
    smali = apk.find_smali('"AdHelper.kt"', '"ro.vendor.oplus.market.name"', package='com/oplus/phonemanager/common/ad').pop()
    specifier = MethodSpecifier()
    specifier.name = 'invoke'
    specifier.return_type = 'Ljava/lang/Boolean;'
    specifier.keywords.add('"ro.vendor.oplus.market.name"')
    new_body = '''\
.method public final invoke()Ljava/lang/Boolean;
    .locals 1

    const/4 v0, 0x0

    invoke-static {v0}, Ljava/lang/Boolean;->valueOf(Z)Ljava/lang/Boolean;

    move-result-object v0

    return-object v0
.end method\
'''
    smali.method_replace(specifier, new_body)

    log('去除手机管家中的安全事件')
    smali = apk.find_smali('MainWithMenuFragment.kt', '"com.coloros.securityguard"', package='com/oplus/phonemanager').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PRIVATE
    specifier.is_final = True
    specifier.parameters = 'Landroid/content/Context;Landroid/view/Menu;'
    specifier.return_type = 'V'
    specifier.keywords.add('"com.coloros.securityguard"')

    old_body = smali.find_method(specifier)
    pattern = r'''
    new-instance [v|p]\d+, Landroid/content/Intent;
(?:.|\n)*?
    invoke-direct {[v|p]\d+}, Landroid/content/Intent;-><init>\(\)V
(?:.|\n)*?
    const-string [v|p]\d+, "coloros\.intent\.action\.SECURITY_GUARD"
(?:.|\n)*?
(    const [v|p]\d+, .+
(?:.|\n)*?
    invoke-interface {[v|p]\d+, [v|p]\d+}, Landroid/view/Menu;->removeItem\(I\)V)
'''
    repl = r'''
\g<1>
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    log('禁用应用安装监控')
    smali = apk.open_smali('com/oplus/phonemanager/virusdetect/receiver/RealTimeMonitorReceiver.smali')
    specifier = MethodSpecifier()
    specifier.name = 'onReceive'
    specifier.parameters = 'Landroid/content/Context;Landroid/content/Intent;'
    smali.method_return_null(specifier)

    log('病毒扫描永远安全')
    smali = apk.find_smali('"InfectedAppDao_Impl.java"', '"select * from infected_app"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.parameters = 'Ljava/util/List;'
    specifier.return_type = 'V'
    specifier.keywords.add('"Lcom/oplus/phonemanager/virusdetect/database/entity/InfectedApp;"')
    specifier.keywords.add('->insert(Ljava/lang/Iterable;)V')
    smali.method_nop(specifier)

    apk.build()


@modified('system_ext/priv-app/TeleService/TeleService.apk')
def patch_tele_service():
    apk = ApkFile('system_ext/priv-app/TeleService/TeleService.apk')
    apk.decode()

    log('显示首选网络类型设置')
    smali = apk.find_smali('"SIMS_OplusSimInfoActivity"', '"changeNetworkModeConfig type:"', package='com/android/simsettings/activity').pop()
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
    smali = apk.find_smali('"SIMS_TrafficCardUtils"', '"clearHighDataSimCardConfiguration"', package='androidx/appcompat/widget').pop()
    specifier = MethodSpecifier()
    specifier.name = 'run'
    specifier.parameters = ''

    old_body = smali.find_method(specifier)
    pattern = r'''
    sget-object [v|p]\d+, Lcom/android/phone/ConfigurationConstants;->INSTANCE:Lcom/android/phone/ConfigurationConstants;

    invoke-virtual {[v|p]\d+}, Lcom/android/phone/ConfigurationConstants;->getTRAFFIC_CARD_PACKAGE_NAME\(\)Ljava/lang/String;

    move-result-object [v|p]\d+

    const-string [v|p]\d+, "basewallet_traffic_card_support"

    const-string [v|p]\d+, "true"

    invoke-static {(?:[v|p]\d+, ){3}[v|p]\d+}, Lcom/android/phone/oplus/share/\S+;->\S+\(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;\)Z

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
    const-string [v|p]\d+, "basewallet_traffic_card_support"

    const-string [v|p]\d+, "true"

    invoke-static {p1(?:, [v|p]\d+){3}}, L\S+;->\S+\(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;\)Z

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
    const-string [v|p]\\d+, "hide_silence_notification_icon_enable"

    invoke-static {}, Lcom/oplus/notificationmanager/config/BaseFeatureOption;->isExpVersion\\(\\)Z

    move-result [v|p]\\d+

    invoke-static {(?:[v|p]\\d+, ){3}[v|p]\\d+}, Lcom/oplus/notificationmanager/view/PerferenceExKt;->\
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
    disable_activity_start_dialog()
    turn_off_flashlight_with_power_key()
    patch_oplus_services()
    patch_system_ui()
    patch_launcher()
    patch_theme_store()
    disable_lock_screen_red_one()
    disable_launcher_clock_red_one()
    show_touchscreen_panel_info()
    show_netmask_and_gateway()
    patch_settings()
    patch_phone_manager()
    patch_tele_service()
    remove_traffic_monitor_ads()
    show_icon_for_silent_notification()
    remove_system_notification_ads()
    remove_calendar_ads()


def run_on_module():
    pass
