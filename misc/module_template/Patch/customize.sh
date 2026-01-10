# Do not try "REPLACE" again, this will invalidate the binding mount
REMOVE="
$var_remove_oat"

enforce_install_from_app() {
	if ! $BOOTMODE; then
		ui_print "*****************************************"
		ui_print "! Install from recovery is NOT supported"
		ui_print "! Please install from module manager app"
		abort "*****************************************"
	fi
}
enforce_install_from_app

appendToScript() {
	echo "$1" >> $MODPATH/post-fs-data.sh
}

removeDataApp() {
	local result=$(pm path "$1")
	if [ -n "$result" ]; then
		local path=$(dirname $(dirname ${result:8}))
		if [ ${path:0:10} = "/data/app/" ]; then
			ui_print "- Update app: $1, remove on next boot: $path"
			appendToScript "rm -rf $path"
		fi
	fi
}

$var_remove_data_app