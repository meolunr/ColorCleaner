package com.meolunr.colorcleaner;

import android.content.pm.PackageInfo;
import android.text.Spannable;
import android.text.SpannableString;
import android.text.TextUtils;
import android.text.style.AbsoluteSizeSpan;
import android.widget.TextView;

public class CcInjector {
    public static void setPackageAndVersion(TextView textView, PackageInfo packageInfo) {
        SpannableString packageName = new SpannableString(packageInfo.packageName);
        int size = (int) (textView.getTextSize() + 6);
        AbsoluteSizeSpan span = new AbsoluteSizeSpan(size);
        packageName.setSpan(span, 0, packageInfo.packageName.length(), Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);

        CharSequence text = TextUtils.concat(packageName, "\n版本 ", packageInfo.versionName, " (", String.valueOf(packageInfo.getLongVersionCode()), ")");
        textView.setText(text);
    }
}