"""Config flow for the Folkbibliotek Sverige integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .axiell_arena_client import (
    ArenaAccountLockedError,
    ArenaClient,
    ArenaError,
    ArenaInvalidCredentialsError,
)
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.core import HomeAssistant

STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): selector.TextSelector(
            selector.TextSelectorConfig(read_only=True)
        ),
        vol.Required(CONF_USERNAME): selector.TextSelector(
            selector.TextSelectorConfig(read_only=True)
        ),
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

DOCS_URL = "https://github.com/emontnemery/folkbibliotek-sverige"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """
    Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        client = ArenaClient(
            session=async_get_clientsession(hass),
            url=data[CONF_URL],
            username=data[CONF_USERNAME],
            password=data[CONF_PASSWORD],
        )

        await client.get_account_overview()
    except ArenaError:
        return {"base": "cannot_connect"}
    except ArenaAccountLockedError:
        return {"base": "account_locked"}
    except ArenaInvalidCredentialsError:
        return {"base": "invalid_credentials"}
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unexpected exception")
        return {"base": "unknown"}
    else:
        return {}


class FolkbibliotekSverigeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Folkbibliotek Sverige."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_URL: user_input[CONF_URL],
                    CONF_USERNAME: user_input[CONF_USERNAME],
                }
            )
            if not (errors := await validate_input(self.hass, user_input)):
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={"docs_url": DOCS_URL},
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        config_entry_data = self._get_reauth_entry().data

        if user_input is not None and not (
            errors := await validate_input(self.hass, user_input)
        ):
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=user_input
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_REAUTH_DATA_SCHEMA,
                {
                    CONF_URL: config_entry_data[CONF_URL],
                    CONF_USERNAME: config_entry_data[CONF_USERNAME],
                },
            ),
            description_placeholders={"docs_url": DOCS_URL},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfigure."""
        errors: dict[str, str] = {}
        config_entry_data = self._get_reconfigure_entry().data

        if user_input is not None and not (
            errors := await validate_input(self.hass, user_input)
        ):
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data_updates=user_input
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_REAUTH_DATA_SCHEMA,
                {
                    CONF_URL: config_entry_data[CONF_URL],
                    CONF_USERNAME: config_entry_data[CONF_USERNAME],
                },
            ),
            description_placeholders={"docs_url": DOCS_URL},
            errors=errors,
        )
