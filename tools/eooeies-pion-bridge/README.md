# EOOEIES Pion bridge

Small helper used by the Home Assistant integration to convert an EOOEIES SmartVideoGo/WebRTC live session into raw Annex-B H264 for local Home Assistant/go2rtc consumption.

The Home Assistant integration starts this helper automatically and provides credentials through environment variables at runtime. Normal users should not run this manually.

## Manual diagnostic run

```bash
EOOEIES_EMAIL="user@example.com" \
EOOEIES_PASSWORD="your-password" \
EOOEIES_SN="camera-serial" \
EOOEIES_RESOLUTION="1280x720" \
EOOEIES_RUNTIME_SECONDS="60" \
./eooeies-bridge > sample.h264
```

Do not publish generated configs, WebRTC tickets, access tokens, or camera serial numbers.
