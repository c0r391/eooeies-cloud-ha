from __future__ import annotations
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import PERCENTAGE
from .const import DOMAIN
from .entity import EooeiesEntity

SENSORS = [
    ("battery", "Battery", "batteryLevel", SensorDeviceClass.BATTERY, PERCENTAGE),
    ("status", "Status", "deviceStatus", None, None),
    ("ip", "IP", "ip", None, None),
    ("last_push_image", "Last Push Image", None, None, None),
]

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    key = (discovery_info or {}).get("entry_key", "yaml")
    await _async_add(hass.data[DOMAIN][key], async_add_entities)

async def async_setup_entry(hass, entry, async_add_entities):
    await _async_add(hass.data[DOMAIN][entry.entry_id], async_add_entities)

async def _async_add(coordinator, async_add_entities):
    entities=[]
    for dev in coordinator.data.get("devices", []):
        sn=dev.get("serialNumber")
        if not sn: continue
        entities.extend(EooeiesSensor(coordinator, sn, *desc) for desc in SENSORS)
    async_add_entities(entities)

class EooeiesSensor(EooeiesEntity, SensorEntity):
    def __init__(self, coordinator, serial, suffix, label, key, device_class, unit):
        super().__init__(coordinator, serial)
        self.suffix=suffix; self.label=label; self.key=key
        self._attr_unique_id=f"eooeies_{serial}_{suffix}"
        self._attr_device_class=device_class
        self._attr_native_unit_of_measurement=unit

    @property
    def name(self):
        return f"{self.device.get('deviceName','EOOEIES')} {self.label}"

    @property
    def native_value(self):
        if self.suffix == "last_push_image":
            return "available" if self.push.get("lastPushImageUrl") else None
        return self.device.get(self.key)

    @property
    def extra_state_attributes(self):
        dev=self.device
        attrs={"serial_number": self.serial, "model": dev.get("displayModelNo"), "firmware": dev.get("firmwareId"), "stream_protocol": (dev.get("deviceSupport") or {}).get("supportStreamProtocol"), "resolution": dev.get("recResolution")}
        if self.suffix == "last_push_image":
            attrs.update({"last_push_time": self.push.get("lastPushTime"), "last_push_image_url": self.push.get("lastPushImageUrl")})
        return attrs
