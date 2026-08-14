from datetime import timedelta
DOMAIN = "eooeies_cloud"
DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)
CONF_REGION = "region"
REGION_EU = "eu"
REGION_US = "us"
BASE_URLS = {REGION_EU: "https://api-eu.eooeies.live", REGION_US: "https://api-us.eooeies.live"}
APP_BODY = {
    "apiVersion": "", "appName": "EOOEIES", "appType": "Android",
    "bundle": "com.mb.eooeies", "countlyId": "", "env": "prod-k8s",
    "tenantId": "eooeies", "timeZone": "Europe/Madrid",
    "version": 202502044, "versionName": "1.0.4",
}
BASE_BODY = {"countryNo": "ES", "language": "de", "tenantId": "eooeies", "app": APP_BODY}
