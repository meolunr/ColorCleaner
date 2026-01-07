package com.meolunr.colorcleaner;

import android.content.pm.PackageInfo;
import android.os.Environment;

import java.io.File;
import java.util.ArrayList;
import java.util.List;

public class CcInjector {
    private static final ArrayList<String> modifiedPackages = new ArrayList<>();

    static {
        modifiedPackages.add("placeholder");  // placeholder
    }

    public static void filterModifiedPackage(List<?> packages) {
        if (new File(Environment.getExternalStorageDirectory(), "cccm").exists())
            return;

        for (Object bean : new ArrayList<>(packages)) {
            String packageName = getPackageName(bean);
            if (modifiedPackages.contains(packageName)) {
                packages.remove(bean);
            }
        }
    }

    private static String getPackageName(Object bean) {
        return ((PackageInfo) bean).getApexPackageName();  // placeholder
    }
}