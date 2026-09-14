"""Tests for the Folkbibliotek Sverige config flow."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
import pytest
import voluptuous as vol

from custom_components.folkbibliotek_sverige.const import DOMAIN

from . import BASE_URL, OVERVIEW_URL, PASSWORD, USERNAME, load_fixture

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import AsyncMock

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )

LOGIN_PARAMS = {"p_p_id": "patronLogin_WAR_arenaportlet"}

# What the user types into the initial form.
USER_INPUT = {
    CONF_NAME: "John Doe",
    CONF_PASSWORD: PASSWORD,
    CONF_URL: BASE_URL,
    CONF_USERNAME: USERNAME,
}

# What the reauth and reconfigure steps actually receive. Their schema exposes
# CONF_URL and CONF_USERNAME as read only text selectors, and the frontend
# strips read only fields from the payload before submitting it
# (frontend src/dialogs/config-flow/step-flow-form.ts, `_submitStep`), so the
# password is the only key that ever reaches the flow. Sending more than this
# would test a payload no UI can produce.
REAUTH_INPUT = {CONF_PASSWORD: "new_password"}

# Login responses which make the client raise, and the error the flow must show.
LOGIN_ERRORS = [
    ("login_failed_wrong_credentials.html", "invalid_credentials"),
    ("login_failed_too_many_attempts.html", "account_locked"),
    ("not_logged_in.html", "cannot_connect"),
]


@pytest.fixture
def mock_arena(aioclient_mock: AiohttpClientMocker) -> Callable[..., None]:
    """
    Return a callable which mocks the Arena service.

    Called without a login response, the overview page is served straight away.
    Called with one, the overview page demands a login and the login POST is
    answered with that fixture.
    """

    def _mock_arena(login_response: str | None = None) -> None:
        aioclient_mock.clear_requests()
        if login_response is None:
            aioclient_mock.get(OVERVIEW_URL, text=load_fixture("logged_in.html"))
            return
        aioclient_mock.get(OVERVIEW_URL, text=load_fixture("not_logged_in.html"))
        aioclient_mock.post(
            OVERVIEW_URL, params=LOGIN_PARAMS, text=load_fixture(login_response)
        )

    return _mock_arena


def suggested_values(data_schema: vol.Schema) -> dict[str, Any]:
    """Return the values the frontend will prefill the form with."""
    return {
        key.schema: key.description["suggested_value"]
        for key in data_schema.schema
        if isinstance(key, vol.Marker)
        and isinstance(key.description, dict)
        and "suggested_value" in key.description
    }


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_arena: Callable[..., None],
) -> None:
    """Test that the user flow works."""
    mock_arena()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert result["options"] == {}
    assert result["result"].unique_id is None
    assert result["title"] == "John Doe"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("enable_custom_integrations", "mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that an entry with the same URL and username is rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        # A different name for the same account must still abort.
        result["flow_id"],
        USER_INPUT | {CONF_NAME: "Jane Doe"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(("login_response", "error"), LOGIN_ERRORS)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_arena: Callable[..., None],
    login_response: str,
    error: str,
) -> None:
    """Test that the user flow shows errors and recovers."""
    mock_arena(login_response)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    # The user corrects the problem and resubmits the same form.
    mock_arena()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("enable_custom_integrations", "mock_setup_entry")
async def test_user_flow_unexpected_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an error which is not an ArenaError is reported as unknown."""
    aioclient_mock.get(OVERVIEW_URL, status=500)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("enable_custom_integrations", "mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_arena: Callable[..., None],
) -> None:
    """Test that the reauth flow works."""
    mock_arena()

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]
    # The read only fields are shown so the user can see which account is being
    # reauthenticated; they are prefilled from the config entry.
    assert suggested_values(result["data_schema"]) == {
        CONF_PASSWORD: PASSWORD,
        CONF_URL: BASE_URL,
        CONF_USERNAME: USERNAME,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    # The flow reloads the entry; let the reload and its delayed
    # storage write finish so no timer outlives the test.
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # Only the password is updated, the rest is carried over from the entry.
    assert mock_config_entry.data == {
        CONF_NAME: "John Doe",
        CONF_PASSWORD: "new_password",
        CONF_URL: BASE_URL,
        CONF_USERNAME: USERNAME,
    }


@pytest.mark.parametrize(("login_response", "error"), LOGIN_ERRORS)
@pytest.mark.usefixtures("enable_custom_integrations", "mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_arena: Callable[..., None],
    login_response: str,
    error: str,
) -> None:
    """Test that the reauth flow shows errors and recovers."""
    mock_arena(login_response)

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}
    # A failed attempt must not touch the stored credentials.
    assert mock_config_entry.data[CONF_PASSWORD] == PASSWORD

    mock_arena()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"


@pytest.mark.usefixtures("enable_custom_integrations", "mock_setup_entry")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_arena: Callable[..., None],
) -> None:
    """Test that the reconfigure flow works."""
    mock_arena()

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert not result["errors"]
    assert suggested_values(result["data_schema"]) == {
        CONF_PASSWORD: PASSWORD,
        CONF_URL: BASE_URL,
        CONF_USERNAME: USERNAME,
    }

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    # The flow reloads the entry; let the reload and its delayed
    # storage write finish so no timer outlives the test.
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # The reconfigure step reuses the reauth schema, so the password is the only
    # thing it can change; the rest is carried over from the entry.
    assert mock_config_entry.data == {
        CONF_NAME: "John Doe",
        CONF_PASSWORD: "new_password",
        CONF_URL: BASE_URL,
        CONF_USERNAME: USERNAME,
    }


@pytest.mark.parametrize(("login_response", "error"), LOGIN_ERRORS)
@pytest.mark.usefixtures("enable_custom_integrations", "mock_setup_entry")
async def test_reconfigure_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_arena: Callable[..., None],
    login_response: str,
    error: str,
) -> None:
    """Test that the reconfigure flow shows errors and recovers."""
    mock_arena(login_response)

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": error}
    # A failed attempt must not touch the stored credentials.
    assert mock_config_entry.data[CONF_PASSWORD] == PASSWORD

    mock_arena()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], REAUTH_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new_password"
