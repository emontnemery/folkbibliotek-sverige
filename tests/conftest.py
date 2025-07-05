"""Test fixtures."""

from collections.abc import Generator
import logging
from unittest.mock import AsyncMock, patch

from aioresponses import aioresponses
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL, CONF_USERNAME
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.folkbibliotek_sverige.const import DOMAIN

from . import BASE_URL, PASSWORD, USERNAME

_LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.folkbibliotek_sverige.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="responses")
def aioresponses_fixture() -> Generator[aioresponses]:
    """Return aioresponses fixture."""
    with aioresponses() as mocked_responses:
        yield mocked_responses


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="John Doe",
        data={
            CONF_NAME: "John Doe",
            CONF_PASSWORD: PASSWORD,
            CONF_URL: BASE_URL,
            CONF_USERNAME: USERNAME,
        },
        unique_id="user@host.com",
    )
