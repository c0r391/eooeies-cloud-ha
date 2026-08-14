from __future__ import annotations

from urllib.parse import urlparse

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.network import get_url

from .const import DOMAIN
from .entity import EooeiesEntity


def _slug(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "camera"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    key = (discovery_info or {}).get("entry_key", "yaml")
    await _async_add(hass, hass.data[DOMAIN][key], key, async_add_entities)


async def async_setup_entry(hass, entry, async_add_entities):
    await _async_add(hass, hass.data[DOMAIN][entry.entry_id], entry.entry_id, async_add_entities)


async def _async_add(hass, coordinator, entry_id, async_add_entities):
    entities = []
    for dev in coordinator.data.get("devices", []):
        serial = dev.get("serialNumber")
        if not serial:
            continue
        entities.append(EooeiesLastEventCamera(coordinator, serial))
        # EOOEIES CG6K devices expose live video via SmartVideoGo WebRTC even
        # when the cloud device-list payload does not include a stable
        # streamType/supportWebrtc flag, so expose a live entity for every
        # camera serial discovered by this integration.
        entities.append(EooeiesLiveCamera(hass, coordinator, entry_id, serial))
    async_add_entities(entities)


class EooeiesLastEventCamera(EooeiesEntity, Camera):
    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator, serial):
        EooeiesEntity.__init__(self, coordinator, serial)
        Camera.__init__(self)
        self._attr_unique_id = f"eooeies_{serial}_last_event"

    @property
    def name(self):
        return f"{self.device.get('deviceName', 'EOOEIES')} Last Event"

    @property
    def is_on(self):
        return True

    async def async_camera_image(self, width=None, height=None):
        url = self.push.get("lastPushImageUrl")
        if not url:
            return None
        return await self.coordinator.client.fetch_image(url)


class EooeiesLiveCamera(EooeiesEntity, Camera):
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_content_type = "video/H264"

    def __init__(self, hass, coordinator, entry_id: str, serial: str):
        EooeiesEntity.__init__(self, coordinator, serial)
        Camera.__init__(self)
        self.hass = hass
        self.entry_id = entry_id
        self._attr_unique_id = f"eooeies_{serial}_live"

    @property
    def go2rtc_stream_name(self) -> str:
        return f"eooeies_{_slug(self.device.get('deviceName') or self.serial[:8])}_live"

    @property
    def extra_state_attributes(self):
        return {"go2rtc_stream": self.go2rtc_stream_name}

    @property
    def name(self):
        return f"{self.device.get('deviceName', 'EOOEIES')} Live"

    @property
    def is_on(self):
        return True

    async def async_camera_image(self, width=None, height=None):
        """Use the last event image as the live entity thumbnail."""
        url = self.push.get("lastPushImageUrl")
        if not url:
            return None
        return await self.coordinator.client.fetch_image(url)

    async def stream_source(self):
        base = get_url(self.hass, allow_internal=True, allow_external=False)
        host = urlparse(base).hostname or "127.0.0.1"
        return f"rtsp://{host}:8554/{self.go2rtc_stream_name}"
