"""Tests for the Folkbibliotek Sverige config flow."""

from unittest.mock import AsyncMock

from aioresponses import aioresponses
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.folkbibliotek_sverige.const import DOMAIN

from . import BASE_URL, PASSWORD, USERNAME, load_fixture


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    responses: aioresponses,
) -> None:
    """Test that the user flow works."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("logged_in.html"),
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "John Doe",
            CONF_PASSWORD: PASSWORD,
            CONF_URL: BASE_URL,
            CONF_USERNAME: USERNAME,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: "John Doe",
        CONF_PASSWORD: PASSWORD,
        CONF_URL: BASE_URL,
        CONF_USERNAME: USERNAME,
    }
    assert result["options"] == {}
    assert result["result"].unique_id is None
    assert result["title"] == "John Doe"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    responses: aioresponses,
) -> None:
    """Test that the reauth flow works."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("logged_in.html"),
    )

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password", CONF_URL: BASE_URL, CONF_USERNAME: USERNAME},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_NAME: "John Doe",
        CONF_PASSWORD: "new_password",
        CONF_URL: BASE_URL,
        CONF_USERNAME: USERNAME,
    }


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    responses: aioresponses,
) -> None:
    """Test that the reconfigure flow works."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("logged_in.html"),
    )

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new_password", CONF_URL: BASE_URL, CONF_USERNAME: USERNAME},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_NAME: "John Doe",
        CONF_PASSWORD: "new_password",
        CONF_URL: BASE_URL,
        CONF_USERNAME: USERNAME,
    }
