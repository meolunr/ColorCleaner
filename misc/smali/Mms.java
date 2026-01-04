package com.meolunr.colorcleaner;

import org.json.JSONArray;
import org.json.JSONObject;

public class CcInjector {
    public static boolean shouldFilterButton(JSONObject entityJson) {
        int showType = entityJson.optInt("showType", -1);
        int channel = entityJson.optInt("channel", -1);

        if (showType == 1 || channel == 1) {
            JSONArray actionsJsonArray = entityJson.optJSONArray("actions");
            for (int i = 0; i < actionsJsonArray.length(); i++) {
                int action = actionsJsonArray.optJSONObject(i).optInt("action");
                if (action == 6) {
                    return true;
                }
            }
        }
        return false;
    }
}