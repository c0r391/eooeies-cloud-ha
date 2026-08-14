from __future__ import annotations
import asyncio
from dataclasses import dataclass
from typing import Any
import aiohttp
from .const import BASE_BODY, BASE_URLS, REGION_EU

class EooeiesError(Exception): pass

@dataclass
class EooeiesClient:
    session: aiohttp.ClientSession
    email: str
    password: str
    region: str = REGION_EU
    token: str | None = None
    user_id: str | None = None
    user_name: str | None = None

    @property
    def base_url(self) -> str:
        return BASE_URLS.get(self.region, BASE_URLS[REGION_EU])

    async def _post(self, path: str, payload: dict[str, Any], *, token: bool = False) -> dict[str, Any]:
        headers = {
            "Content-Type": "application/json; charset=UTF-8",
            "Accept": "application/json",
            "User-Agent": "EOOEIES/1.0.4 (202502044; Android; Home Assistant)",
        }
        if token and self.token:
            headers["Authorization"] = self.token
        async with self.session.post(self.base_url + path, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()
            if resp.status >= 400:
                raise EooeiesError(f"HTTP {resp.status}: {text[:200]}")
            data = await resp.json(content_type=None)
        if data.get("result") != 0:
            raise EooeiesError(f"{path}: {data.get('msg')} ({data.get('result')})")
        return data

    async def login(self) -> None:
        payload = dict(BASE_BODY)
        payload.update({"email": self.email, "password": self.password, "loginType": 0})
        data = await self._post("/account/login/", payload)
        login = data["data"]
        self.token = login["token"]["token"]
        self.user_id = str(login.get("id"))
        self.user_name = login.get("name")

    async def async_validate(self) -> dict[str, Any]:
        await self.login()
        return {"user_id": self.user_id, "user_name": self.user_name}

    async def fetch(self) -> dict[str, Any]:
        if not self.token:
            await self.login()
        try:
            devices = (await self._post("/device/listuserdevices", dict(BASE_BODY), token=True))["data"].get("list", [])
        except EooeiesError:
            self.token = None
            await self.login()
            devices = (await self._post("/device/listuserdevices", dict(BASE_BODY), token=True))["data"].get("list", [])
        push = (await self._post("/device/devicePushImage", dict(BASE_BODY), token=True))["data"]
        push_by_sn = {item.get("serialNumber"): item for item in push if item.get("serialNumber")}
        return {"devices": devices, "push": push_by_sn}

    async def fetch_image(self, url: str) -> bytes:
        async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            return await resp.read()
