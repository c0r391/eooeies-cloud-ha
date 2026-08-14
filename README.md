# EOOEIES Cloud Cameras for Home Assistant

A Home Assistant custom integration for EOOEIES cloud battery cameras.

This integration connects to the EOOEIES cloud account used by the mobile app and exposes camera status, battery information, last event images, and live video in Home Assistant.

> Beta notice: live video has been validated with EOOEIES CG6K-style cameras and the shared Video Bridge add-on. Please test on a non-critical Home Assistant instance before using it in production.

## Features

- EOOEIES cloud login through the app-compatible cloud API
- Device discovery from your EOOEIES account
- Battery, status, IP, and awake/connectivity entities
- Last event image camera entities
- Live camera entities using the EOOEIES SmartVideoGo/WebRTC path
- Automatic configuration of the shared **TP-Link Unified Video Bridge** add-on when available
- Fallback dynamic go2rtc stream publishing for older bridge add-on versions

## Requirements

### Required

- Home Assistant OS or Supervised Home Assistant is recommended.
- An EOOEIES account that already works in the EOOEIES mobile app.
- Network access from Home Assistant to the EOOEIES cloud API.

### Required for live video

Install and start the shared video bridge add-on:

```text
https://github.com/c0r391/tplink-unified-video-addon
```

The add-on is intentionally shared by multiple integrations:

- **TP-Link Unified** configures TP-Link/Tapo streams.
- **EOOEIES Cloud Cameras** configures EOOEIES streams.

You normally do not edit the add-on YAML manually. Install and start the add-on once, then configure cameras in the integration UI.

### Architecture note

The shared add-on currently keeps the name **TP-Link Unified Video Bridge** for compatibility with existing TP-Link/Tapo users, but it is now a universal camera video bridge for TP-Link/Tapo and EOOEIES.

## Installation with HACS

1. Install the shared Video Bridge add-on first:
   - Home Assistant → Settings → Add-ons → Add-on Store.
   - Three-dot menu → Repositories.
   - Add:
     ```text
     https://github.com/c0r391/tplink-unified-video-addon
     ```
   - Install **TP-Link Unified Video Bridge**.
   - Start the add-on.

2. Add this integration to HACS:
   - HACS → Integrations → three-dot menu → Custom repositories.
   - Repository:
     ```text
     https://github.com/c0r391/eooeies-cloud-ha
     ```
   - Category: **Integration**.
   - Install **EOOEIES Cloud Cameras**.

3. Restart Home Assistant.

4. Add the integration:
   - Settings → Devices & services → Add integration.
   - Search for **EOOEIES Cloud Cameras**.
   - Enter:
     - EOOEIES account email
     - EOOEIES account password
     - Region (`eu` or `us`)

5. Wait for entities to appear.

## Configuration

The integration asks for the same EOOEIES account you use in the mobile app.

| Field | Description |
| --- | --- |
| Email | EOOEIES account email address |
| Password | EOOEIES account password |
| Region | Cloud region. Use `eu` for European accounts and `us` for US accounts |

Credentials are stored in Home Assistant's normal config entry storage. They are not written to the Video Bridge add-on options. The add-on receives only local Home Assistant bridge URLs for EOOEIES streams.

## Entities

For each camera, the integration creates entities similar to:

| Entity type | Example | Description |
| --- | --- | --- |
| Camera | `camera.front_live` | Live video stream through go2rtc / Home Assistant stream |
| Camera | `camera.front_last_event` | Last event image from EOOEIES cloud |
| Sensor | `sensor.front_battery` | Battery percentage |
| Sensor | `sensor.front_status` | Raw cloud status value |
| Sensor | `sensor.front_ip` | Camera IP reported by EOOEIES cloud |
| Sensor | `sensor.front_last_push_image` | Last event image availability |
| Binary sensor | `binary_sensor.front_awake` | Camera awake/connectivity flag |

Entity names depend on the camera names returned by EOOEIES.

## Live video behavior

The integration exposes local raw-H264 bridge endpoints in Home Assistant and registers go2rtc streams with names like:

```text
eooeies_front_live
```

When the shared Video Bridge add-on supports persistent EOOEIES options (`eooeies_cameras`, add-on `0.1.2+`), the integration writes those options through the Supervisor API.

For older add-on versions, the integration keeps a fallback that periodically re-publishes only its own `eooeies_*` streams to go2rtc. It does not overwrite TP-Link/Tapo streams.

## Troubleshooting

### No live video

Check:

1. The shared Video Bridge add-on is installed and running.
2. `http://<home-assistant-host>:1984/api/schemes` is reachable and contains `tapo`.
3. Home Assistant has been restarted after installing the integration.
4. The EOOEIES account works in the mobile app.
5. The camera is awake/online.

### Status works but live video does not

Status and last event images use normal EOOEIES cloud API calls. Live video additionally requires:

- EOOEIES cloud live-video ticket retrieval
- SmartVideoGo/WebRTC bridge process
- go2rtc stream registration
- Home Assistant `stream` support

Restart the shared Video Bridge add-on and Home Assistant, then check Home Assistant logs for `eooeies_cloud` messages.

### TP-Link/Tapo streams disappeared

This integration should not remove TP-Link/Tapo streams. The shared Video Bridge add-on keeps TP-Link/Tapo `cameras` and EOOEIES `eooeies_cameras` separately. If TP-Link/Tapo streams disappear, check the Video Bridge add-on options and update to the latest add-on release.

## Security and privacy

- Do not share Home Assistant logs publicly without checking for account names or local details.
- EOOEIES account credentials stay in the Home Assistant config entry.
- EOOEIES live streams are proxied locally through Home Assistant and go2rtc.
- The integration does not require RTSP, ONVIF, or VicoHome credentials.

## Known limitations

- This is a beta release.
- The bundled live-video bridge binary is Linux amd64 and is built as a static binary for Home Assistant OS compatibility. Other architectures need a matching external bridge binary at `/config/eooeies/eooeies-bridge`.
- The beta.2 bridge improves H.264 packet handling to reduce visible macroblock artifacts from incomplete RTP fragments.
- Audio for EOOEIES live video is not claimed as verified in this release.
- Cloud/API changes by EOOEIES may require integration updates.

## Support this project

If this integration is useful for your dashboard or automation setup, BTC support is appreciated and helps keep the project maintained.

```text
bc1qqe5l9e36h49wm9kkjrek7v746gej3s3j2hrkgd
```

## Credits

This integration is independent and is not affiliated with EOOEIES, ADDX, TP-Link, Tapo, Home Assistant, or go2rtc.
