import io
import os
import re
import shutil
import sys
from glob import glob
from pathlib import Path
from zipfile import ZipFile

import ccglobal
import config
from build.apkfile import ApkFile
from build.smali import MethodSpecifier
from util import template

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
                ccglobal.log(f'删除文件: {item}')
                if os.path.isdir(item):
                    shutil.rmtree(item)
                else:
                    os.remove(item)
            else:
                ccglobal.log(f'文件不存在: {item}')


def replace_analytics():
    ccglobal.log('替换 BlankAnalytics')
    shutil.rmtree('product/app/AnalyticsCore')

    blank_dir = 'product/app/BlankAnalytics'
    os.makedirs(blank_dir)
    shutil.copy(f'{ccglobal.MISC_DIR}/BlankAnalytics.apk', blank_dir)


def disable_signature_verification():
    ccglobal.log('禁用 V3 签名完整性验证')
    apk = ApkFile('system/system/framework/framework.jar')
    apk.decode()

    smali = apk.open_smali('android/util/apk/ApkSigningBlockUtils.smali')
    specifier = MethodSpecifier()
    specifier.name = 'parseVerityDigestAndVerifySourceLength'
    specifier.parameters = '[BJLandroid/util/apk/SignatureInfo;'
    specifier.return_type = '[B'
    new_body = '''\
.method static blacklist parseVerityDigestAndVerifySourceLength([BJLandroid/util/apk/SignatureInfo;)[B
    .locals 2

    const/4 v0, 0x0

    const/16 v1, 0x20

    invoke-static {p0, v0, v1}, Ljava/util/Arrays;->copyOfRange([BII)[B

    move-result-object v0

    return-object v0
.end method
'''
    smali.method_replace(specifier, new_body)

    specifier = MethodSpecifier()
    specifier.name = 'verifyIntegrityForVerityBasedAlgorithm'
    specifier.parameters = '[BLjava/io/RandomAccessFile;Landroid/util/apk/SignatureInfo;'
    smali.method_nop(specifier)

    apk.build()
    os.remove(f'{apk.file}.fsv_meta')
    for file in glob('system/system/framework/**/boot-framework.*', recursive=True):
        if not os.path.samefile(apk.file, file):
            os.remove(file)


def patch_miui_services():
    apk = ApkFile('system_ext/framework/miui-services.jar')
    apk.decode()

    ccglobal.log('禁用关联启动对话框')
    smali = apk.open_smali('miui/app/ActivitySecurityHelper.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getCheckStartActivityIntent'
    old_body = smali.find_method(specifier)
    pattern = r'if-eqz p6, :cond_\S+'
    match = re.search(pattern, old_body)
    new_body = old_body.replace(match.group(0), '')
    smali.method_replace(old_body, new_body)

    ccglobal.log('禁用主题自动恢复')
    smali = apk.open_smali('com/android/server/am/ActivityManagerServiceImpl.smali')
    specifier = MethodSpecifier()
    specifier.name = 'finishBooting'
    specifier.parameters = ''
    old_body = smali.find_method(specifier)
    pattern = r'''
    invoke-static {[v|p]\d+}, Lmiui/drm/DrmBroadcast;->getInstance\(Landroid/content/Context;\)Lmiui/drm/DrmBroadcast;

    move-result-object [v|p]\d+

    invoke-virtual {[v|p]\d+}, Lmiui/drm/DrmBroadcast;->broadcast\(\)V
'''
    new_body = re.sub(pattern, '', old_body)
    smali.method_replace(old_body, new_body)

    apk.build()
    os.remove(f'{apk.file}.fsv_meta')
    for file in glob('system_ext/framework/oat/arm64/miui-services.*'):
        if not os.path.samefile(apk.file, file):
            os.remove(file)


@modified('system_ext/priv-app/MiuiSystemUI/MiuiSystemUI.apk')
def disable_historical_notification():
    apk = ApkFile('system_ext/priv-app/MiuiSystemUI/MiuiSystemUI.apk')
    apk.decode()

    ccglobal.log('禁用历史通知')
    smali = apk.open_smali('com/miui/systemui/notification/MiuiBaseNotifUtil.smali')
    specifier = MethodSpecifier()
    specifier.name = 'shouldSuppressFold'
    smali.method_return_boolean(specifier, True)

    smali = apk.open_smali('com/android/systemui/statusbar/notification/collection/coordinator/FoldCoordinator.smali')
    specifier.name = 'attach'
    specifier.parameters = 'Lcom/android/systemui/statusbar/notification/collection/NotifPipeline;'
    smali.method_nop(specifier)

    apk.build()


@modified('product/priv-app/MIUIPackageInstaller/MIUIPackageInstaller.apk')
def patch_package_installer():
    ccglobal.log('去除应用包管理组件广告')
    apk = ApkFile('product/priv-app/MIUIPackageInstaller/MIUIPackageInstaller.apk')
    apk.refactor()
    apk.decode(False)

    # Remove ads
    smali = apk.open_smali('com/miui/packageInstaller/model/ApkInfo.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getSystemApp'
    smali.method_return_boolean(specifier, True)

    # Disable ads switch by default
    smali = apk.find_smali('"ads_enable"').pop()
    specifier = MethodSpecifier()
    specifier.return_type = 'Z'
    specifier.keywords.add('"ads_enable"')
    smali.method_return_boolean(specifier, False)

    # Turn on the safe mode UI without enabling its features
    smali = apk.find_smali('"ro.miui.customized.region"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.is_static = True
    specifier.parameters = 'Landroid/content/Context;'
    specifier.return_type = 'Z'
    specifier.keywords.add('"safe_mode_is_open_cloud_config"')
    body = smali.find_method(specifier)
    safe_mode_method = re.search(r'\.method public static (\S+)\n', body).group(1)
    call_instruction = f'{smali.get_type_signature()}->{safe_mode_method}'

    smali = apk.find_smali('"FullSafeHelper"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.is_final = True
    specifier.parameters = ''
    specifier.return_type = 'Z'
    specifier.keywords.add(call_instruction)
    smali.method_return_boolean(specifier, True)

    ccglobal.log('允许应用包管理组件安装系统应用')
    smali = apk.find_smali('"PackageUtil"', '"getPackageVersionCode"').pop()
    specifier = MethodSpecifier()
    specifier.parameters = 'Landroid/content/Context;Ljava/lang/String;'
    specifier.return_type = 'Z'
    specifier.keywords.add('getApplicationInfo')
    smali.method_return_boolean(specifier, False)

    # Hide outdated switches
    xml = apk.open_xml('xml/settings.xml')
    root = xml.get_root()
    for element in root.findall('.//miuix.preference.CheckBoxPreference'):
        if element.get(xml.make_attr_key('android:key')) == 'pref_key_open_ads':
            element.set(xml.make_attr_key('app:isPreferenceVisible'), 'false')
    for element in root.findall('.//miuix.preference.TextPreference'):
        if element.get(xml.make_attr_key('android:key')) == 'pref_key_security_mode_security_verify_risk_app':
            element.set(xml.make_attr_key('app:isPreferenceVisible'), 'false')
    xml.commit()

    # Hide feedback button
    xml = apk.open_xml('menu/full_safe_installer_prepare_action_bar.xml')
    group_tree = xml.get_root().find('group')
    for element in group_tree.findall('item'):
        if element.get(xml.make_attr_key('android:id')) == '@id/feedback':
            group_tree.remove(element)
    xml.commit()

    apk.build()


@modified('product/app/MIUIThemeManager/MIUIThemeManager.apk')
def patch_theme_manager():
    apk = ApkFile('product/app/MIUIThemeManager/MIUIThemeManager.apk')
    apk.decode()

    ccglobal.log('去除主题商店广告')
    smali = apk.open_smali('com/android/thememanager/basemodule/ad/model/AdInfoResponse.smali')
    specifier = MethodSpecifier()
    specifier.name = 'isAdValid'
    smali.method_return_boolean(specifier, False)

    # Filter advertising elements
    smali = apk.find_smali('Lcom/android/thememanager/recommend/model/entity/element/DetailRecommendElement;', package='com/android/thememanager/recommend/model/adapter/factory').pop()
    specifier = MethodSpecifier()
    specifier.parameters = 'Lcom/android/thememanager/router/recommend/entity/UICard;'
    specifier.return_type = 'Ljava/util/List;'

    old_body = smali.find_method(specifier)
    pattern = r'''
    :goto_(\S+)
    invoke-interface {p1}, Ljava/util/Iterator;->hasNext\(\)Z
'''
    match = re.search(pattern, old_body)
    goto = match.group(1)
    pattern = r'''
    check-cast ([v|p]\d+), Lcom/android/thememanager/router/recommend/entity/UIImageWithLink;
(?:.|\n)*?
    const/4 ([v|p]\d+), 0x1
'''
    repl = f'''\
    check-cast \\g<1>, Lcom/android/thememanager/router/recommend/entity/UIImageWithLink;

    iget-object \\g<2>, \\g<1>, Lcom/android/thememanager/router/recommend/entity/UIImageWithLink;->adInfo:Lcom/android/thememanager/basemodule/ad/model/AdInfoResponse;

    if-nez \\g<2>, :goto_{goto}

    const/4 \\g<2>, 0x1
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    ccglobal.log('破解主题免费')
    smali = apk.open_smali('com/android/thememanager/detail/theme/model/OnlineResourceDetail.smali')
    specifier = MethodSpecifier()
    specifier.name = 'toResource'
    specifier.return_type = 'Lcom/android/thememanager/basemodule/resource/model/Resource;'
    insert = '''\
    const/4 v0, 0x1
    
    iput-boolean v0, p0, Lcom/android/thememanager/detail/theme/model/OnlineResourceDetail;->bought:Z
'''
    smali.method_insert_before(specifier, insert)

    smali = apk.open_smali('com/android/thememanager/basemodule/views/DiscountPriceView.smali')
    specifier = MethodSpecifier()
    specifier.name = 'setPrice'
    specifier.parameters = 'II'
    insert = '''\
    const/4 p1, 0x0

    const/4 p2, 0x0
'''
    smali.method_insert_before(specifier, insert)

    smali = apk.find_smali('"theme"', '"check rights isLegal: "').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
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


@modified('system_ext/priv-app/AuthManager/AuthManager.apk')
def disable_sensitive_word_check():
    ccglobal.log('禁用设备名称敏感词检查')
    apk = ApkFile('system_ext/priv-app/AuthManager/AuthManager.apk')
    apk.decode()

    smali = apk.open_smali('com/miui/privacy/WNProvider.smali')
    specifier = MethodSpecifier()
    specifier.name = 'call'
    specifier.parameters = 'Ljava/lang/String;Ljava/lang/String;Landroid/os/Bundle;'
    specifier.return_type = 'Landroid/os/Bundle;'
    old_body = smali.find_method(specifier)
    new_body = '''\
.method public call(Ljava/lang/String;Ljava/lang/String;Landroid/os/Bundle;)Landroid/os/Bundle;
    .locals 4

    const/4 p2, 0x0

    if-eqz p3, :cond_0

    new-instance v0, Landroid/os/Bundle;

    invoke-direct {v0}, Landroid/os/Bundle;-><init>()V

    const-string v1, "key_state"

    const/4 v2, 0x0

    invoke-virtual {v0, v1, v2}, Landroid/os/Bundle;->putInt(Ljava/lang/String;I)V

    const-string v1, "key_has_ques"

    invoke-virtual {v0, v1, v2}, Landroid/os/Bundle;->putBoolean(Ljava/lang/String;Z)V

    invoke-static {p1}, Ljava/lang/Integer;->parseInt(Ljava/lang/String;)I

    move-result v1

    if-nez v1, :cond_1

    return-object v0

    :cond_1
    const/4 v2, 0x1

    if-ne v1, v2, :cond_0

    invoke-static {}, Landroid/os/Message;->obtain()Landroid/os/Message;

    move-result-object v2

    invoke-virtual {v2, v0}, Landroid/os/Message;->setData(Landroid/os/Bundle;)V

    const-string v3, "callback"

    invoke-virtual {p3, v3}, Landroid/os/Bundle;->getParcelable(Ljava/lang/String;)Landroid/os/Parcelable;

    move-result-object v3

    check-cast v3, Landroid/os/Messenger;

    if-eqz v3, :cond_0

    :try_start_0
    invoke-virtual {v3, v2}, Landroid/os/Messenger;->send(Landroid/os/Message;)V
    :try_end_0
    .catch Landroid/os/RemoteException; {:try_start_0 .. :try_end_0} :catch_0

    goto :goto_0

    :catch_0
    move-exception p3

    :cond_0
    :goto_0
    return-object p2
.end method
'''
    smali.method_replace(old_body, new_body)

    apk.build()


@modified('product/priv-app/MIUISecurityCenter/MIUISecurityCenter.apk')
def patch_security_center():
    apk = ApkFile('product/priv-app/MIUISecurityCenter/MIUISecurityCenter.apk')
    apk.decode()

    ccglobal.log('去除应用信息举报按钮')
    smali = apk.open_smali('com/miui/appmanager/fragment/ApplicationsDetailsFragment.smali')
    specifier = MethodSpecifier()
    specifier.parameters = 'Landroid/content/Context;Landroid/net/Uri;'
    specifier.return_type = 'Z'
    specifier.keywords.add('"android.intent.action.VIEW"')
    specifier.keywords.add('"com.xiaomi.market"')
    smali.method_return_boolean(specifier, False)

    ccglobal.log('显示电池健康度')
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
(?:.|\n)*?
    move-result [v|p]\\d+
(?:.|\n)*?
    if-eqz [v|p]\\d+, :cond_\\S+
(?:.|\n)*?
    invoke-static {{}}, {utils_type_signature}->{re.escape(method_signature_2)}
(?:.|\n)*?
    move-result ([v|p]\\d+)
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

    ccglobal.log('显示电池温度')
    smali = apk.open_smali('com/miui/powercenter/nightcharge/ChargeProtectFragment.smali')
    specifier = MethodSpecifier()
    specifier.parameters = 'Landroid/content/Context;'
    specifier.return_type = 'Ljava/lang/String;'
    specifier.is_static = True
    specifier.keywords.add('-0x80000000')
    old_body = smali.find_method(specifier)

    pattern = r'''
    invoke-static {p0}, \S+;->\S+\(Landroid/content/Context;\)I
(?:.|\n)*?
    move-result ([v|p]\d+)
(?:.|\n)*?
    invoke-static {p0}, \S+;->\S+\(Landroid/content/Context;\)I
(?:.|\n)*?
    move-result ([v|p]\d+)
(?:.|\n)*?
    const/high16 [v|p]\d+, -0x80000000
(?:.|\n)*?
    const/4 ([v|p]\d+), 0x5
(?:.|\n)*?
    if-le [v|p]\d+, \3, (:cond_\d+)
(?:.|\n)*?
    :cond_\d+
    move \1, \2
(?:.|\n)*?
    \4
'''
    match = re.search(pattern, old_body)
    register1 = match.group(1)
    register2 = match.group(2)
    cond = match.group(4)

    pattern = f'''\
    {cond}
(?:.|\\n)*?
.end method'''
    repl = f'''\
    {cond}
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

    ccglobal.log('禁用手机管家立即修复')
    smali = apk.open_smali('com/miui/securityscan/ui/main/MainContentFrame.smali')
    specifier = MethodSpecifier()
    specifier.name = 'onClick'
    specifier.parameters = 'Landroid/view/View;'
    smali.method_nop(specifier)

    ccglobal.log('显示详细耗电数据')
    # Show battery usage data for all apps
    smali = apk.find_smali('"PowerRankHelperHolder"', '"getBatteryUsageStats"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.is_static = True
    specifier.parameters = ''
    specifier.return_type = 'Z'
    specifier.keywords.add('sget-boolean')
    specifier.keywords.add('Lcom/miui/powercenter/legacypowerrank/')
    smali.method_return_boolean(specifier, False)

    # Show battery usage data for touchscreen
    specifier.access = MethodSpecifier.Access.PRIVATE
    smali.method_return_boolean(specifier, False)

    # Hide unknown battery usage data
    specifier.keywords.clear()
    specifier.keywords.add('"ishtar"')
    specifier.keywords.add('"nuwa"')
    specifier.keywords.add('"fuxi"')
    smali.method_return_boolean(specifier, True)

    ccglobal.log('禁用耗电项优化建议')
    smali = apk.find_smali('"key_show_battery_power_save_suggest"').pop()
    specifier = MethodSpecifier()
    specifier.is_static = True
    specifier.return_type = 'Z'
    specifier.keywords.add('"key_show_battery_power_save_suggest"')
    smali.method_return_boolean(specifier, False)

    ccglobal.log('禁用 Root 权限检查')
    smali = apk.find_smali('"key_check_item_root"').pop()
    specifier = MethodSpecifier()
    specifier.is_static = True
    specifier.return_type = 'Z'
    specifier.keywords.add('"key_check_item_root"')
    smali.method_return_boolean(specifier, False)

    ccglobal.log('禁用 ADB 安装确认')
    smali = apk.find_smali('"permcenter_install_intercept_enabled"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.return_type = 'Z'
    specifier.keywords.add('"permcenter_install_intercept_enabled"')
    smali.method_return_boolean(specifier, False)

    ccglobal.log('去除危险操作倒计时确认')
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


@modified('system/system/priv-app/TeleService/TeleService.apk')
def show_network_type_settings():
    ccglobal.log('显示首选网络类型设置')
    apk = ApkFile('system/system/priv-app/TeleService/TeleService.apk')
    apk.decode()

    smali = apk.open_smali('com/android/phone/NetworkModeManager.smali')
    specifier = MethodSpecifier()
    specifier.name = 'isRemoveNetworkModeSettings'

    specifier.parameters = 'I'
    smali.method_return_boolean(specifier, False)
    specifier.parameters = 'Lcom/android/internal/telephony/Phone;'
    smali.method_return_boolean(specifier, False)

    apk.build()


@modified('product/priv-app/MiuiMms/MiuiMms.apk')
def remove_mms_ads():
    apk = ApkFile('product/priv-app/MiuiMms/MiuiMms.apk')
    apk.decode()

    ccglobal.log('去除短信输入框广告')
    smali = apk.open_smali('com/miui/smsextra/ui/BottomMenu.smali')
    specifier = MethodSpecifier()
    specifier.name = 'allowMenuMode'
    specifier.return_type = 'Z'
    smali.method_return_boolean(specifier, False)

    ccglobal.log('去除短信下方广告')
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.name = 'setHideButton'

    insert = '''\
    const/4 p1, 0x1
'''
    for smali in apk.find_smali('.method public setHideButton(Z)V'):
        smali.method_insert_before(specifier, insert)

    apk.build()


@modified('product/app/MiTrustService/MiTrustService.apk')
def disable_mi_trust_service_mrm():
    ccglobal.log('禁用 Mrm 风险检测')
    apk = ApkFile('product/app/MiTrustService/MiTrustService.apk')
    apk.decode()

    smali = apk.find_smali('"MiTrustService/statusEventHandle"', '"try init mrmd Service"').pop()
    specifier = MethodSpecifier()
    specifier.access = MethodSpecifier.Access.PUBLIC
    specifier.is_final = True
    specifier.parameters = ''
    specifier.return_type = 'Z'
    specifier.keywords.add('"MiTrustService/statusEventHandle"')
    specifier.keywords.add('"try init mrmd Service"')
    smali.method_return_boolean(specifier, False)

    apk.build()


@modified('product/app/MIUISuperMarket/MIUISuperMarket.apk')
def ignore_modified_app_update():
    ccglobal.log('忽略修改过的系统应用更新')
    apk = ApkFile('product/app/MIUISuperMarket/MIUISuperMarket.apk')
    apk.decode()
    apk.add_smali(f'{ccglobal.MISC_DIR}/smali/MIUISuperMarket.smali', 'com/meolunr/colorcleaner/Template.smali')

    smali = apk.open_smali('com/xiaomi/market/data/LocalAppManager.smali')
    specifier = MethodSpecifier()
    specifier.name = 'getUpdateInfoFromServer'
    old_body = smali.find_method(specifier)
    pattern = r'''
    invoke-direct/range {p0 .. p0}, Lcom/xiaomi/market/data/LocalAppManager;->loadInvalidSystemPackageList\(\)Ljava/util/List;

    move-result-object ([v|p]\d+)
'''
    repl = r'''\g<0>
    invoke-static {\g<1>}, Lcom/meolunr/colorcleaner/CcInjector;->addModifiedPackages(Ljava/util/List;)V
'''
    new_body = re.sub(pattern, repl, old_body)
    smali.method_replace(old_body, new_body)

    output = io.StringIO()
    for package in config.MODIFY_PACKAGE:
        output.write(f'const-string v1, "{package}"\n\n')
        output.write('invoke-interface {p0, v1}, Ljava/util/List;->add(Ljava/lang/Object;)Z\n\n')

    # If the cccm (ColorCleaner Check Modified) file exists in the root directory of internal storage, skip package filtering
    template_smali_path = apk.open_smali('com/meolunr/colorcleaner/Template.smali').file
    template.substitute(template_smali_path, f'{os.path.dirname(template_smali_path)}/CcInjector.smali', var_modified_package=output.getvalue())
    os.remove(template_smali_path)

    apk.build()


def run_on_rom():
    rm_files()
    replace_analytics()
    disable_signature_verification()
    patch_miui_services()
    disable_historical_notification()
    patch_package_installer()
    patch_theme_manager()
    disable_sensitive_word_check()
    patch_security_center()
    show_network_type_settings()
    remove_mms_ads()
    disable_mi_trust_service_mrm()
    ignore_modified_app_update()


def run_on_module():
    disable_historical_notification()
    patch_package_installer()
    patch_theme_manager()
    disable_sensitive_word_check()
    patch_security_center()
    show_network_type_settings()
    remove_mms_ads()
    disable_mi_trust_service_mrm()
    ignore_modified_app_update()
