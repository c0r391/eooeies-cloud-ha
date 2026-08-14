from __future__ import annotations
import logging
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
_LOGGER = logging.getLogger(__name__)

class EooeiesCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, client, scan_interval=DEFAULT_SCAN_INTERVAL):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=scan_interval)
        self.client = client

    async def _async_update_data(self):
        try:
            return await self.client.fetch()
        except Exception as err:
            raise UpdateFailed(str(err)) from err
