from __future__ import annotations
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

class EooeiesEntity(CoordinatorEntity):
    def __init__(self, coordinator, serial: str):
        super().__init__(coordinator)
        self.serial = serial

    @property
    def device(self):
        for dev in self.coordinator.data.get("devices", []):
            if dev.get("serialNumber") == self.serial:
                return dev
        return {}

    @property
    def push(self):
        return self.coordinator.data.get("push", {}).get(self.serial) or {}

    @property
    def device_info(self):
        dev = self.device
        return DeviceInfo(
            identifiers={(DOMAIN, self.serial)},
            name=dev.get("deviceName") or self.serial,
            manufacturer="EOOEIES",
            model=dev.get("displayModelNo"),
            sw_version=dev.get("firmwareId"),
        )
