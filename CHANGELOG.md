# Changelog

## 0.1.0-beta.7

- Avoid unnecessary shared Video Bridge add-on restarts when EOOEIES stream options are already current.
- Use the shared add-on's persistent EOOEIES stream configuration as the primary path instead of also pushing dynamic duplicate go2rtc updates.
- Add more camera entities for Wi-Fi signal, firmware, network, SD card, charging, online/watch-live status, live-audio support, recording-audio status, and detection/support flags.
- Add an experimental MPEG-TS bridge endpoint with AAC audio for diagnostics; Home Assistant/go2rtc still uses the more stable raw-H264 path by default until the audio path is fully stable.

## 0.1.0-beta.6

- Improve live-stream continuity by keeping the WebRTC signaling connection alive instead of ending the bridge on idle signaling timeouts.
- Send periodic camera/data-channel keepalive commands during live sessions.
- Continue periodic RTCP keyframe requests during the live session to improve recovery after stalls.
- Validation: 75-120 second EOOEIES captures completed without H.264 corruption artifacts; remaining beta limitation is variable cloud-camera frame cadence.

## 0.1.0-beta.5

- Scrub public wording so documentation and package metadata contain no personal names, private environment labels, or test-system references.


## 0.1.0-beta.4

- Fix Home Assistant thread-safety warning by starting the go2rtc keepalive as a named background task from a callback-safe context.

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
