from __future__ import annotations
import logging
import voluptuous as vol
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from .addon import async_configure_video_addon
from .api import EooeiesClient
from .const import CONF_REGION, DEFAULT_SCAN_INTERVAL, DOMAIN, REGION_EU
from .coordinator import EooeiesCoordinator
from .live import async_configure_go2rtc_streams, async_register_live_view, async_unload_go2rtc_streams
_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "binary_sensor", "camera"]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_EMAIL): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_REGION, default=REGION_EU): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    conf = config.get(DOMAIN)
    if not conf:
        return True
    session = async_get_clientsession(hass)
    client = EooeiesClient(session, conf[CONF_EMAIL], conf[CONF_PASSWORD], conf.get(CONF_REGION, REGION_EU))
    coordinator = EooeiesCoordinator(hass, client, conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    await coordinator.async_refresh()
    hass.data.setdefault(DOMAIN, {})["yaml"] = coordinator
    await async_register_live_view(hass)
    addon_configured = await async_configure_video_addon(hass, "yaml", coordinator)
    if not addon_configured:
        await async_configure_go2rtc_streams(hass, "yaml", coordinator)
    for platform in PLATFORMS:
        hass.async_create_task(async_load_platform(hass, platform, DOMAIN, {"entry_key": "yaml"}, config))
    return True

async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    session = async_get_clientsession(hass)
    client = EooeiesClient(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], entry.data.get(CONF_REGION, REGION_EU))
    coordinator = EooeiesCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await async_register_live_view(hass)
    addon_configured = await async_configure_video_addon(hass, entry.entry_id, coordinator)
    if not addon_configured:
        await async_configure_go2rtc_streams(hass, entry.entry_id, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await async_unload_go2rtc_streams(hass, entry.entry_id)
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok
