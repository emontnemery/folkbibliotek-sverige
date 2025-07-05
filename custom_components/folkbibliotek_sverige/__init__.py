"""
The Folkbibliotek Sverige custom integration.

For more details about this integration, please refer to
https://github.com/emontnemery/folkbibliotek-sverige
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .axiell_arena_client import ArenaClient
from .coordinator import FolkbibliotekSverigeDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


_PLATFORMS: list[Platform] = [Platform.TODO]

type FolkbibliotekSverigeConfigEntry = ConfigEntry[FolkbibliotekSverigeData]


@dataclass(frozen=True)
class FolkbibliotekSverigeData:
    """FolkbibliotekSverige data class."""

    coordinator: FolkbibliotekSverigeDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: FolkbibliotekSverigeConfigEntry
) -> bool:
    """Set up Folkbibliotek Sverige from a config entry."""
    client = ArenaClient(
        session=async_get_clientsession(hass),
        url=entry.data["url"],
        username=entry.data["username"],
        password=entry.data["password"],
    )

    coordinator = FolkbibliotekSverigeDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = FolkbibliotekSverigeData(coordinator=coordinator)

    entry.async_on_unload(entry.add_update_listener(update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: FolkbibliotekSverigeConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def update_listener(
    hass: HomeAssistant, entry: FolkbibliotekSverigeConfigEntry
) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
