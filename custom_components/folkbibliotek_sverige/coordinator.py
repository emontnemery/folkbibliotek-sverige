"""DataUpdateCoordinator for the Folkbibliotek Sverige integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .axiell_arena_client import (
    ArenaAccountLockedError,
    ArenaClient,
    ArenaError,
    ArenaInvalidCredentialsError,
    LibraryLoan,
    LibraryReservation,
    LibraryReservationReady,
)
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import FolkbibliotekSverigeConfigEntry


@dataclass(frozen=True, kw_only=True)
class FolkbibliotekSverigeData:
    """Analytics data class."""

    loans: list[LibraryLoan]
    active_reservations: list[LibraryReservation]
    waiting_reservations: list[
        LibraryReservationReady
    ]  # Rename to LibraryWaitingReservation


class FolkbibliotekSverigeDataUpdateCoordinator(
    DataUpdateCoordinator[FolkbibliotekSverigeData]
):
    """Folkbibliotek Sverige data update coordinator."""

    config_entry: FolkbibliotekSverigeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: FolkbibliotekSverigeConfigEntry,
        client: ArenaClient,
    ) -> None:
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=2),
        )
        self._client = client

    async def _async_update_data(self) -> FolkbibliotekSverigeData:
        if isinstance(self.last_exception, ConfigEntryAuthFailed):
            # If the last exception was a ConfigEntryAuthFailed, we should not try
            # to update again, or the account will be locked.
            LOGGER.warning(
                "Authentication failed, not trying to update again. "
                "Please check your credentials and try again."
            )
            raise self.last_exception
        try:
            overview = await self._client.get_account_overview()
        except (ArenaAccountLockedError, ArenaInvalidCredentialsError) as err:
            raise ConfigEntryAuthFailed(err) from err
        except ArenaError as err:
            raise UpdateFailed("Error communicating with the library database") from err  # noqa: EM101, TRY003
        LOGGER.debug("loans: %s", self._client.get_loans(overview))
        LOGGER.debug(
            "active reservations: %s", self._client.get_active_reservations(overview)
        )
        LOGGER.debug(
            "ready reservations: %s", self._client.get_ready_reservations(overview)
        )
        return FolkbibliotekSverigeData(
            loans=self._client.get_loans(overview),
            active_reservations=self._client.get_active_reservations(overview),
            waiting_reservations=self._client.get_ready_reservations(overview),
        )
