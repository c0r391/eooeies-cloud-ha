# Changelog

## 0.1.0-beta.3

- Start the periodic go2rtc keepalive republisher only after Home Assistant has completed startup.
- Avoids Home Assistant startup timeout warnings from the intentionally long-lived EOOEIES stream keepalive task.

## 0.1.0-beta.2

- Rebuilt the bundled EOOEIES Pion bridge as a static Linux amd64 binary for Home Assistant OS compatibility.
- Fixed H.264 depacketizing for STAP-A parameter sets and packet-loss/reorder handling.
- Drops incomplete fragmented NAL units instead of forwarding partial frames, reducing visible macroblock artifacts.
- Validated 40–60 second RTSP samples from both test cameras with no H.264 corruption errors.

## 0.1.0-beta.1

- Initial HACS beta release.
- Adds EOOEIES account config flow, device sensors, last-event image cameras, and live camera entities through the shared video bridge add-on.
