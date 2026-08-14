from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from .const import DOMAIN
from .entity import EooeiesEntity

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    key=(discovery_info or {}).get("entry_key","yaml")
    await _async_add(hass.data[DOMAIN][key], async_add_entities)
async def async_setup_entry(hass, entry, async_add_entities):
    await _async_add(hass.data[DOMAIN][entry.entry_id], async_add_entities)
async def _async_add(coordinator, async_add_entities):
    async_add_entities([EooeiesAwakeSensor(coordinator, d["serialNumber"]) for d in coordinator.data.get("devices", []) if d.get("serialNumber")])

class EooeiesAwakeSensor(EooeiesEntity, BinarySensorEntity):
    _attr_device_class=BinarySensorDeviceClass.CONNECTIVITY
    def __init__(self, coordinator, serial):
        super().__init__(coordinator, serial)
        self._attr_unique_id=f"eooeies_{serial}_awake"
    @property
    def name(self): return f"{self.device.get('deviceName','EOOEIES')} Awake"
    @property
    def is_on(self): return bool(self.device.get("awake"))
