from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import EooeiesClient, EooeiesError
from .const import CONF_REGION, DOMAIN, REGION_EU, REGION_US

class EooeiesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            client = EooeiesClient(async_get_clientsession(self.hass), user_input[CONF_EMAIL], user_input[CONF_PASSWORD], user_input.get(CONF_REGION, REGION_EU))
            try:
                info = await client.async_validate()
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(f"eooeies_{info.get('user_id') or user_input[CONF_EMAIL]}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"EOOEIES {info.get('user_name') or user_input[CONF_EMAIL]}", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_REGION, default=REGION_EU): vol.In([REGION_EU, REGION_US]),
            }),
            errors=errors,
        )
