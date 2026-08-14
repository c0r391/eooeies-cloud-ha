from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import quote, urlparse

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

_LOGGER = logging.getLogger(__name__)

VIDEO_ADDON_SLUG = "431fa582_tplink_unified_video"
VIDEO_ADDON_PUBLIC_URL = "https://github.com/c0r391/tplink-unified-video-addon"


def _slug(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "camera"


async def async_configure_video_addon(hass: HomeAssistant, entry_id: str, coordinator) -> bool:
    """Best-effort: add EOOEIES cameras to the shared Video Bridge add-on.

    HACS installs this integration, not Home Assistant add-ons. If Marcel/the
    user has installed the shared TP-Link Unified Video Bridge add-on, configure
    its EOOEIES section through Supervisor while preserving existing TP-Link
    camera options.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    supervisor = os.environ.get("SUPERVISOR", "http://supervisor")
    if not token:
        _LOGGER.info(
            "Shared Video Bridge add-on auto-configuration is only available on Home Assistant OS/Supervised"
        )
        return False
    if not supervisor.startswith(("http://", "https://")):
        supervisor = f"http://{supervisor}"

    try:
        base = get_url(hass, allow_internal=True, allow_external=False).rstrip("/")
    except Exception:  # noqa: BLE001
        base = "http://127.0.0.1:8123"

    eooeies_cameras: list[dict[str, str]] = []
    for dev in coordinator.data.get("devices", []):
        serial = dev.get("serialNumber")
        if not serial:
            continue
        stream_name = f"eooeies_{_slug(dev.get('deviceName') or serial[:8])}_live"
        eooeies_cameras.append(
            {
                "name": stream_name,
                "source": f"{base}/api/eooeies_cloud/live/{entry_id}/{quote(serial)}.h264",
            }
        )

    if not eooeies_cameras:
        return False

    session = async_get_clientsession(hass)
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with session.get(f"{supervisor}/addons/{VIDEO_ADDON_SLUG}/info", headers=headers, timeout=15) as response:
            if response.status == 404:
                _LOGGER.info(
                    "Shared Video Bridge add-on is not installed. Install it from %s for smooth EOOEIES video.",
                    VIDEO_ADDON_PUBLIC_URL,
                )
                return False
            response.raise_for_status()
            payload = await response.json()
    except Exception as err:  # noqa: BLE001
        _LOGGER.info("Could not inspect shared Video Bridge add-on: %s", err)
        return False

    addon_data = payload.get("data", {}) if isinstance(payload, dict) else {}
    options: dict[str, Any] = dict(addon_data.get("options") or {})
    supports_persistent_eooeies = "eooeies_cameras" in options or _version_at_least(
        str(addon_data.get("version") or "0.0.0"), "0.1.2"
    )
    existing = list(options.get("eooeies_cameras") or [])
    by_name = {item.get("name"): item for item in existing if isinstance(item, dict) and item.get("name")}
    for item in eooeies_cameras:
        by_name[item["name"]] = item
    options.setdefault("log_level", "info")
    options["eooeies_cameras"] = list(by_name.values())

    try:
        async with session.post(
            f"{supervisor}/addons/{VIDEO_ADDON_SLUG}/options",
            headers=headers,
            json={"options": options},
            timeout=15,
        ) as response:
            response.raise_for_status()
        action = "restart" if addon_data.get("state") == "started" else "start"
        async with session.post(
            f"{supervisor}/addons/{VIDEO_ADDON_SLUG}/{action}",
            headers=headers,
            json={},
            timeout=20,
        ) as response:
            if response.status >= 400 and action == "restart":
                async with session.post(
                    f"{supervisor}/addons/{VIDEO_ADDON_SLUG}/start",
                    headers=headers,
                    json={},
                    timeout=20,
                ) as start_response:
                    start_response.raise_for_status()
            else:
                response.raise_for_status()
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Could not update shared Video Bridge add-on options for EOOEIES: %s", err)
        return False

    if supports_persistent_eooeies:
        _LOGGER.info("Configured %d persistent EOOEIES stream(s) in the shared Video Bridge add-on", len(eooeies_cameras))
        return True

    _LOGGER.info(
        "Shared Video Bridge add-on accepted EOOEIES options but does not advertise persistent eooeies_cameras support; keeping dynamic go2rtc republish fallback active"
    )
    return False


def _version_at_least(version: str, minimum: str) -> bool:
    """Return True when a simple dotted version is >= minimum."""
    def parts(value: str) -> tuple[int, ...]:
        parsed: list[int] = []
        for item in value.split("."):
            digits = "".join(ch for ch in item if ch.isdigit())
            parsed.append(int(digits or 0))
        return tuple(parsed)

    return parts(version) >= parts(minimum)
