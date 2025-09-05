from __future__ import annotations

import asyncio
from aiohttp import web, WSMsgType
from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import DOMAIN


class VncProxyView(HomeAssistantView):
    """Proxy VNC traffic over a Home Assistant websocket."""

    url = "/api/vnc/{entry_id}"
    name = "api:vnc"
    requires_auth = True

    def __init__(self, hass: HomeAssistant, config: dict[str, str | int]):
        self.hass = hass
        self.config = config

    async def get(self, request: web.Request, entry_id: str):
        if entry_id != self.config["entry_id"]:
            return web.Response(status=404)
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        reader, writer = await asyncio.open_connection(
            self.config[CONF_HOST], self.config[CONF_PORT]
        )

        async def ws_to_tcp() -> None:
            async for msg in ws:
                if msg.type == WSMsgType.BINARY:
                    writer.write(msg.data)
                    await writer.drain()

        async def tcp_to_ws() -> None:
            try:
                while True:
                    data = await reader.read(1024)
                    if not data:
                        break
                    await ws.send_bytes(data)
            finally:
                await ws.close()

        await asyncio.gather(ws_to_tcp(), tcp_to_ws())
        writer.close()
        await writer.wait_closed()
        return ws


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VNC from a config entry."""
    config = {
        "entry_id": entry.entry_id,
        CONF_HOST: entry.data[CONF_HOST],
        CONF_PORT: entry.data[CONF_PORT],
    }
    view = VncProxyView(hass, config)
    hass.http.register_view(view)
    static_path = hass.config.path("custom_components/vnc/static")
    hass.http.register_static_path(
        f"/vnc_static/{entry.entry_id}", static_path, cache_headers=False
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = view

    hass.components.frontend.async_register_built_in_panel(
        "iframe",
        {"url": f"/vnc_static/{entry.entry_id}/index.html?entry={entry.entry_id}"},
        sidebar_title=entry.title or entry.data[CONF_HOST],
        sidebar_icon="mdi:monitor",
        panel_id=entry.entry_id,
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.components.frontend.async_remove_panel(entry.entry_id)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    hass.http.unregister_path(f"/vnc_static/{entry.entry_id}")
    return True
