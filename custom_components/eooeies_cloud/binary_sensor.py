from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import EooeiesEntity


@dataclass(frozen=True)
class EooeiesBinarySensorDescription:
    key: str
    label: str
    value: Callable[[dict[str, Any]], bool | None]
    device_class: BinarySensorDeviceClass | None = None
    icon: str | None = None


BINARY_SENSORS: tuple[EooeiesBinarySensorDescription, ...] = (
    EooeiesBinarySensorDescription("awake", "Awake", lambda dev: _bool_int(dev.get("awake")), BinarySensorDeviceClass.CONNECTIVITY),
    EooeiesBinarySensorDescription("online", "Online", lambda dev: _bool_int(dev.get("online")), BinarySensorDeviceClass.CONNECTIVITY),
    EooeiesBinarySensorDescription("can_watch_live", "Can Watch Live", lambda dev: _bool(dev.get("canWatchLive")), icon="mdi:video-check"),
    EooeiesBinarySensorDescription("charging", "Charging", lambda dev: _bool_int(dev.get("isCharging")), BinarySensorDeviceClass.BATTERY_CHARGING),
    EooeiesBinarySensorDescription("live_audio", "Live Audio", lambda dev: _bool(dev.get("liveAudioToggleOn")), icon="mdi:microphone"),
    EooeiesBinarySensorDescription("recording_audio", "Recording Audio", lambda dev: _bool(dev.get("recordingAudioToggleOn")), icon="mdi:microphone-outline"),
    EooeiesBinarySensorDescription("person_detection", "Person Detection", lambda dev: _bool_int(dev.get("personDetect")), BinarySensorDeviceClass.MOTION),
    EooeiesBinarySensorDescription("object_detection_supported", "Object Detection Supported", lambda dev: _bool(dev.get("isSupportObjectDetection")), icon="mdi:motion-sensor"),
    EooeiesBinarySensorDescription("object_detection_enabled", "Object Detection Enabled", lambda dev: _bool(dev.get("isEnabledObjectDetection")), icon="mdi:motion-sensor"),
    EooeiesBinarySensorDescription("push_ignored", "Push Ignored", lambda dev: _bool(dev.get("pushIgnored")), icon="mdi:bell-off"),
    EooeiesBinarySensorDescription("ota_ignored", "OTA Ignored", lambda dev: _bool_int(dev.get("otaIgnored")), icon="mdi:update"),
    EooeiesBinarySensorDescription("anti_theft_alarm", "Anti-theft Alarm", lambda dev: _bool(dev.get("alarmWhenRemoveToggleOn")), BinarySensorDeviceClass.SAFETY),
    EooeiesBinarySensorDescription("antiflicker_supported", "Anti-flicker Supported", lambda dev: _bool(dev.get("antiflickerSupport")), icon="mdi:lightning-bolt"),
)


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _bool_int(value: Any) -> bool | None:
    if value is None:
        return None
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return bool(value)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    key = (discovery_info or {}).get("entry_key", "yaml")
    await _async_add(hass.data[DOMAIN][key], async_add_entities)


async def async_setup_entry(hass, entry, async_add_entities):
    await _async_add(hass.data[DOMAIN][entry.entry_id], async_add_entities)


async def _async_add(coordinator, async_add_entities):
    entities = []
    for dev in coordinator.data.get("devices", []):
        serial = dev.get("serialNumber")
        if not serial:
            continue
        entities.extend(EooeiesBinarySensor(coordinator, serial, desc) for desc in BINARY_SENSORS)
    async_add_entities(entities)


class EooeiesBinarySensor(EooeiesEntity, BinarySensorEntity):
    def __init__(self, coordinator, serial, description: EooeiesBinarySensorDescription):
        super().__init__(coordinator, serial)
        self.description = description
        self._attr_unique_id = f"eooeies_{serial}_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_icon = description.icon

    @property
    def name(self):
        return f"{self.device.get('deviceName', 'EOOEIES')} {self.description.label}"

    @property
    def is_on(self):
        return self.description.value(self.device)
