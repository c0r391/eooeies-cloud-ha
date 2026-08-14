from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT

from .const import DOMAIN
from .entity import EooeiesEntity


def _sd_card_value(dev: dict[str, Any], key: str) -> Any:
    sd_card = dev.get("sdCard")
    if isinstance(sd_card, dict):
        return sd_card.get(key)
    return None


@dataclass(frozen=True)
class EooeiesSensorDescription:
    key: str
    label: str
    value: Callable[[dict[str, Any], dict[str, Any]], Any]
    device_class: SensorDeviceClass | None = None
    unit: str | None = None
    icon: str | None = None


SENSORS: tuple[EooeiesSensorDescription, ...] = (
    EooeiesSensorDescription("battery", "Battery", lambda dev, push: dev.get("batteryLevel"), SensorDeviceClass.BATTERY, PERCENTAGE),
    EooeiesSensorDescription("status", "Status", lambda dev, push: dev.get("deviceStatus"), icon="mdi:list-status"),
    EooeiesSensorDescription("ip", "IP", lambda dev, push: dev.get("ip"), icon="mdi:ip-network"),
    EooeiesSensorDescription("firmware", "Firmware", lambda dev, push: dev.get("firmwareId"), icon="mdi:chip"),
    EooeiesSensorDescription("newest_firmware", "Newest Firmware", lambda dev, push: dev.get("newestFirmwareId"), icon="mdi:update"),
    EooeiesSensorDescription("mcu_firmware", "MCU Firmware", lambda dev, push: dev.get("mcuNumber"), icon="mdi:chip"),
    EooeiesSensorDescription("wifi_signal", "Wi-Fi Signal", lambda dev, push: dev.get("signalStrength"), SensorDeviceClass.SIGNAL_STRENGTH, SIGNAL_STRENGTH_DECIBELS_MILLIWATT),
    EooeiesSensorDescription("wifi_level", "Wi-Fi Level", lambda dev, push: dev.get("signalLevel"), icon="mdi:wifi"),
    EooeiesSensorDescription("wifi_channel", "Wi-Fi Channel", lambda dev, push: dev.get("wifiChannel"), icon="mdi:wifi-cog"),
    EooeiesSensorDescription("network_name", "Network Name", lambda dev, push: dev.get("networkName"), icon="mdi:wifi-settings"),
    EooeiesSensorDescription("charging_mode", "Charging Mode", lambda dev, push: dev.get("chargingMode"), icon="mdi:battery-charging"),
    EooeiesSensorDescription("live_speaker_volume", "Live Speaker Volume", lambda dev, push: dev.get("liveSpeakerVolume"), unit=PERCENTAGE, icon="mdi:volume-high"),
    EooeiesSensorDescription("recording_resolution", "Recording Resolution", lambda dev, push: dev.get("recResolution"), icon="mdi:video"),
    EooeiesSensorDescription("codec", "Codec", lambda dev, push: dev.get("codec"), icon="mdi:file-video"),
    EooeiesSensorDescription("sd_card_total", "SD Card Total", lambda dev, push: _sd_card_value(dev, "total"), icon="mdi:sd"),
    EooeiesSensorDescription("sd_card_used", "SD Card Used", lambda dev, push: _sd_card_value(dev, "used"), icon="mdi:sd"),
    EooeiesSensorDescription("sd_card_free", "SD Card Free", lambda dev, push: _sd_card_value(dev, "free"), icon="mdi:sd"),
    EooeiesSensorDescription("sd_card_format_status", "SD Card Format Status", lambda dev, push: _sd_card_value(dev, "formatStatus"), icon="mdi:sd"),
    EooeiesSensorDescription("last_push_image", "Last Push Image", lambda dev, push: "available" if push.get("lastPushImageUrl") else None, icon="mdi:image"),
)


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
        entities.extend(EooeiesSensor(coordinator, serial, desc) for desc in SENSORS)
    async_add_entities(entities)


class EooeiesSensor(EooeiesEntity, SensorEntity):
    def __init__(self, coordinator, serial, description: EooeiesSensorDescription):
        super().__init__(coordinator, serial)
        self.description = description
        self._attr_unique_id = f"eooeies_{serial}_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.unit
        self._attr_icon = description.icon

    @property
    def name(self):
        return f"{self.device.get('deviceName', 'EOOEIES')} {self.description.label}"

    @property
    def native_value(self):
        return self.description.value(self.device, self.push)

    @property
    def extra_state_attributes(self):
        dev = self.device
        support = dev.get("deviceSupport") or {}
        attrs = {
            "serial_number": self.serial,
            "model": dev.get("displayModelNo"),
            "firmware": dev.get("firmwareId"),
            "stream_protocol": support.get("supportStreamProtocol"),
            "resolution": dev.get("recResolution"),
            "supports_webrtc": support.get("supportWebrtc"),
            "supports_live_audio": support.get("supportLiveAudioToggle"),
            "supports_speaker_volume": support.get("supportLiveSpeakerVolume"),
        }
        if self.description.key == "last_push_image":
            attrs.update({"last_push_time": self.push.get("lastPushTime"), "last_push_image_url": self.push.get("lastPushImageUrl")})
        return attrs
