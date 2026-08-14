from __future__ import annotations

import asyncio
import logging
import os
import platform
from pathlib import Path
from urllib.parse import quote, urlparse

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

EXTERNAL_BRIDGE_PATH = Path("/config/eooeies/eooeies-bridge")
BUNDLED_BRIDGE_PATH = Path(__file__).parent / "bin" / "eooeies-bridge-linux-amd64"
VIEW_REGISTERED = "_live_view_registered"
KEEPALIVE_TASK = "_go2rtc_keepalive_task"


async def async_register_live_view(hass: HomeAssistant) -> None:
    """Register the raw H264 live proxy endpoint once."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(VIEW_REGISTERED):
        return
    hass.http.register_view(EooeiesLiveH264View)
    data[VIEW_REGISTERED] = True


async def async_configure_go2rtc_streams(
    hass: HomeAssistant,
    entry_id: str,
    coordinator,
    *,
    keepalive: bool = True,
) -> None:
    """Best-effort: publish EOOEIES raw-H264 endpoints as go2rtc streams.

    Release architecture is the shared Video Bridge add-on owning persistent
    ``eooeies_cameras`` options. The direct go2rtc PUT path remains a fallback
    for older add-on versions or diagnostics.
    """
    await _async_configure_go2rtc_streams_once(hass, entry_id, coordinator)
    # The shared Video Bridge add-on may still be restarting while HA starts.
    # Retry shortly after startup so add-on-generated go2rtc.yaml does not wipe
    # the dynamically registered EOOEIES streams.
    for delay in (15, 45):
        hass.async_create_task(_async_configure_go2rtc_streams_later(hass, entry_id, coordinator, delay))

    if not keepalive:
        return

    data = hass.data.setdefault(DOMAIN, {})
    task_key = f"{KEEPALIVE_TASK}_{entry_id}"

    def _start_keepalive(_event=None) -> None:
        task = data.get(task_key)
        if task is None or task.done():
            data[task_key] = hass.async_create_task(
                _async_configure_go2rtc_streams_forever(hass, entry_id, coordinator)
            )

    # Do not create the forever keepalive task during integration setup. Home
    # Assistant tracks setup-created tasks and can report a startup timeout even
    # though this periodic republisher is intentionally long-lived.
    if hass.is_running:
        _start_keepalive()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _start_keepalive)


async def async_unload_go2rtc_streams(hass: HomeAssistant, entry_id: str) -> None:
    """Stop periodic go2rtc re-publishing for an unloaded entry."""
    task_key = f"{KEEPALIVE_TASK}_{entry_id}"
    task = hass.data.get(DOMAIN, {}).pop(task_key, None)
    if task:
        task.cancel()


async def _async_configure_go2rtc_streams_forever(hass: HomeAssistant, entry_id: str, coordinator) -> None:
    """Re-publish go2rtc streams after shared add-on restarts.

    The Video Bridge add-on regenerates go2rtc.yaml on every restart. Until the
    add-on natively persists eooeies_cameras, this keepalive re-adds the
    EOOEIES raw-H264 sources without touching TP-Link/Tapo streams.
    """
    try:
        while True:
            await asyncio.sleep(10)
            await _async_configure_go2rtc_streams_once(hass, entry_id, coordinator)
    except asyncio.CancelledError:
        return


async def _async_configure_go2rtc_streams_later(
    hass: HomeAssistant, entry_id: str, coordinator, delay: int
) -> None:
    await asyncio.sleep(delay)
    await _async_configure_go2rtc_streams_once(hass, entry_id, coordinator)


async def _async_configure_go2rtc_streams_once(hass: HomeAssistant, entry_id: str, coordinator) -> None:
    """Publish EOOEIES raw-H264 endpoints as go2rtc streams once.

    The shared Video Bridge/go2rtc add-on is the smooth-player path. If go2rtc
    is present on the default port, persist stream sources there. Failure is not
    fatal: the raw H264 endpoint remains available for diagnostics.
    """
    try:
        base = get_url(hass, allow_internal=True, allow_external=False).rstrip("/")
    except Exception:  # noqa: BLE001
        base = "http://127.0.0.1:8123"
    host = urlparse(base).hostname or "127.0.0.1"
    go2rtc_api = f"http://{host}:1984/api/streams"
    session = async_get_clientsession(hass)
    for dev in coordinator.data.get("devices", []):
        serial = dev.get("serialNumber")
        if not serial:
            continue
        name = f"eooeies_{_slug(dev.get('deviceName') or serial[:8])}_live"
        src = f"{base}/api/eooeies_cloud/live/{entry_id}/{serial}.h264"
        url = f"{go2rtc_api}?name={quote(name)}&src={quote(src, safe='')}"
        try:
            async with session.put(url, timeout=15) as response:
                if response.status >= 400:
                    text = await response.text()
                    _LOGGER.warning("Could not configure go2rtc stream %s: HTTP %s %s", name, response.status, text[:160])
                else:
                    _LOGGER.info("Configured go2rtc stream %s for EOOEIES camera", name)
        except Exception as err:  # noqa: BLE001
            _LOGGER.info("go2rtc not available for EOOEIES stream %s: %s", name, err)


def _slug(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_") or "camera"


class EooeiesLiveH264View(HomeAssistantView):
    """Raw Annex-B H264 endpoint backed by the Go/Pion bridge."""

    url = "/api/eooeies_cloud/live/{entry_id}/{serial}.h264"
    name = "api:eooeies_cloud:live_h264"
    requires_auth = False

    async def get(self, request, entry_id: str, serial: str) -> web.StreamResponse:
        hass: HomeAssistant = request.app["hass"]
        coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
        if coordinator is None:
            raise web.HTTPNotFound(text="unknown EOOEIES entry")

        bridge_path = _bridge_path()
        if bridge_path is None:
            raise web.HTTPNotFound(text="EOOEIES bridge binary not installed")

        try:
            os.chmod(bridge_path, 0o755)
        except OSError as err:
            _LOGGER.warning("Could not chmod EOOEIES bridge binary: %s", err)

        client = coordinator.client
        env = os.environ.copy()
        env.update(
            {
                "EOOEIES_EMAIL": client.email,
                "EOOEIES_PASSWORD": client.password,
                "EOOEIES_SN": serial,
                "EOOEIES_RESOLUTION": "1280x720",
                "EOOEIES_RUNTIME_SECONDS": "300",
            }
        )

        proc = await asyncio.create_subprocess_exec(
            str(bridge_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "video/H264",
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )
        await response.prepare(request)

        async def _log_stderr() -> None:
            assert proc.stderr is not None
            while True:
                line = await proc.stderr.readline()
                if not line:
                    break
                text = line.decode(errors="replace").strip()
                if text:
                    # Bridge logs do not include tokens/passwords; keep them concise.
                    _LOGGER.debug("EOOEIES bridge %s: %s", serial, text)

        stderr_task = hass.loop.create_task(_log_stderr())
        try:
            assert proc.stdout is not None
            while True:
                chunk = await proc.stdout.read(64 * 1024)
                if not chunk:
                    break
                await response.write(chunk)
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            raise
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    proc.kill()
                    await proc.wait()
            stderr_task.cancel()

        return response


def _bridge_path() -> Path | None:
    """Return the preferred EOOEIES Pion bridge binary path.

    `/config/eooeies/eooeies-bridge` allows advanced users to override the
    bundled bridge. The HACS package includes an amd64 Linux bridge for standard
    HAOS/Test-HA installs; other architectures need a matching external binary.
    """
    if EXTERNAL_BRIDGE_PATH.exists():
        return EXTERNAL_BRIDGE_PATH
    if platform.machine().lower() in {"x86_64", "amd64"} and BUNDLED_BRIDGE_PATH.exists():
        return BUNDLED_BRIDGE_PATH
    return None
