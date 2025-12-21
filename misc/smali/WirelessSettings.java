package com.meolunr.colorcleaner;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.LinkAddress;
import android.net.LinkProperties;
import android.net.RouteInfo;
import android.net.wifi.WifiManager;

import androidx.preference.Preference;

import java.net.Inet4Address;
import java.net.InetAddress;
import java.util.ArrayList;

public class CcInjector {
    public static void showNetmaskAndGateway(Context context, Preference ipAddressPreference, Preference ipv4AddressPreference, Preference ipv6AddressPreference) {
        boolean hasIpv4Address = ipv4AddressPreference.isVisible();
        boolean hasIpv6Address = ipv6AddressPreference.isVisible();

        if (hasIpv4Address && hasIpv6Address) {
            CharSequence ipv4Address = ipv4AddressPreference.getSummary();
            CharSequence ipv6Address = ipv6AddressPreference.getSummary();
            String ipAddress = String.valueOf(ipv4Address) + '\n' + ipv6Address;
            ipAddressPreference.setVisible(true);
            ipAddressPreference.setSummary(ipAddress);
        }

        ConnectivityManager connectivityManager = context.getSystemService(ConnectivityManager.class);
        WifiManager wifiManager = context.getSystemService(WifiManager.class);
        LinkProperties linkProperties = connectivityManager.getLinkProperties(wifiManager.getCurrentNetwork());

        if (hasIpv4Address) {
            for (LinkAddress linkAddress : linkProperties.getLinkAddresses()) {
                if (linkAddress.getAddress() instanceof Inet4Address) {
                    int maskInt = 0xFFFFFFFF << (32 - linkAddress.getPrefixLength());
                    int[] arr = new int[]{(maskInt >> 24) & 0xFF, (maskInt >> 16) & 0xFF, (maskInt >> 8) & 0xFF, maskInt & 0xFF};
                    ipv4AddressPreference.setVisible(true);
                    ipv4AddressPreference.setTitle("子网掩码");
                    ipv4AddressPreference.setSummary(String.format("%d.%d.%d.%d", arr[0], arr[1], arr[2], arr[3]));
                    break;
                }
            }
        } else {
            ipv4AddressPreference.setVisible(false);
        }

        ArrayList<String> gateways = new ArrayList<>();
        for (RouteInfo routeInfo : linkProperties.getRoutes()) {
            if (!routeInfo.isDefaultRoute()) continue;

            InetAddress gateway = routeInfo.getGateway();
            if (gateway instanceof Inet4Address) {
                gateways.add(0, gateway.getHostAddress());
            } else {
                gateways.add(gateway.getHostAddress());
            }

            if (gateways.size() == 2)
                break;
        }

        if (!gateways.isEmpty()) {
            ipv6AddressPreference.setVisible(true);
            ipv6AddressPreference.setTitle("网关");
            ipv6AddressPreference.setSummary(String.join("\n", gateways));
        } else {
            ipv6AddressPreference.setVisible(false);
        }
    }
}