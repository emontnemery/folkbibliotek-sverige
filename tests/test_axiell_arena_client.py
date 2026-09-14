"""Test the Axiell Arena client."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from custom_components.folkbibliotek_sverige.axiell_arena_client import (
    ArenaAccountLockedError,
    ArenaClient,
    ArenaInvalidCredentialsError,
    ArenaLoginError,
)

from . import BASE_URL, OVERVIEW_URL, PASSWORD, USERNAME, load_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMocker,
    )
    from syrupy import SnapshotAssertion

LOGIN_PARAMS = {"p_p_id": "patronLogin_WAR_arenaportlet"}

# Expected request counts: one GET of the overview page, plus the login POSTs.
# These are spelled out rather than derived from the client's LOGIN_ATTEMPTS so
# that changing the retry budget has to be an explicit decision here too.
CALLS_ONE_LOGIN = 2
CALLS_EXHAUSTED_LOGINS = 4


@pytest.fixture
async def client(aioclient_mock: AiohttpClientMocker) -> AsyncGenerator[ArenaClient]:
    """Return an Axiell Arena client."""
    async with aioclient_mock.create_session(asyncio.get_running_loop()) as session:
        yield ArenaClient(
            session=session, url=BASE_URL, username=USERNAME, password=PASSWORD
        )


async def test_success(
    aioclient_mock: AiohttpClientMocker,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful retrieval of account overview."""
    aioclient_mock.get(OVERVIEW_URL, text=load_fixture("logged_in.html"))

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == snapshot
    assert client.get_active_reservations(overview) == []
    assert client.get_ready_reservations(overview) == []


async def test_success_no_loans(
    aioclient_mock: AiohttpClientMocker,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful retrieval of account overview with no checked out media."""
    aioclient_mock.get(OVERVIEW_URL, text=load_fixture("logged_in_no_loans.html"))

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == []
    assert client.get_active_reservations(overview) == snapshot
    assert client.get_ready_reservations(overview) == []


async def test_success_no_reservations(
    aioclient_mock: AiohttpClientMocker,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful retrieval of account overview with no holds."""
    aioclient_mock.get(
        OVERVIEW_URL, text=load_fixture("logged_in_no_reservations.html")
    )

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == snapshot
    assert client.get_active_reservations(overview) == []
    assert client.get_ready_reservations(overview) == []


async def test_success_reservation_to_pick_up(
    aioclient_mock: AiohttpClientMocker,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful retrieval of account overview with hold to pick up."""
    aioclient_mock.get(
        OVERVIEW_URL, text=load_fixture("logged_in_reservation_to_pick_up.html")
    )

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == snapshot
    assert client.get_active_reservations(overview) == []
    assert client.get_ready_reservations(overview) == snapshot


async def test_success_need_login(
    aioclient_mock: AiohttpClientMocker,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test log in."""
    aioclient_mock.get(OVERVIEW_URL, text=load_fixture("not_logged_in.html"))
    aioclient_mock.post(
        OVERVIEW_URL, params=LOGIN_PARAMS, text=load_fixture("logged_in.html")
    )

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == snapshot
    assert client.get_active_reservations(overview) == []
    assert client.get_ready_reservations(overview) == []

    # One GET, then a single login POST carrying the configured credentials.
    assert aioclient_mock.call_count == CALLS_ONE_LOGIN
    method, _url, data, _headers = aioclient_mock.mock_calls[1]
    assert method == "POST"
    assert data["openTextUsernameContainer:openTextUsername"] == USERNAME
    assert data["textPassword"] == PASSWORD


async def test_no_login(
    aioclient_mock: AiohttpClientMocker,
    client: ArenaClient,
) -> None:
    """Test no log in."""
    aioclient_mock.get(OVERVIEW_URL, text=load_fixture("not_logged_in.html"))
    aioclient_mock.post(
        OVERVIEW_URL, params=LOGIN_PARAMS, text=load_fixture("not_logged_in.html")
    )

    with pytest.raises(ArenaLoginError):
        await client.get_account_overview()

    # One GET, then three login POSTs before giving up.
    assert aioclient_mock.call_count == CALLS_EXHAUSTED_LOGINS


async def test_account_locked(
    aioclient_mock: AiohttpClientMocker,
    client: ArenaClient,
) -> None:
    """Test account is locked."""
    aioclient_mock.get(OVERVIEW_URL, text=load_fixture("not_logged_in.html"))
    aioclient_mock.post(
        OVERVIEW_URL,
        params=LOGIN_PARAMS,
        text=load_fixture("login_failed_too_many_attempts.html"),
    )

    with pytest.raises(ArenaAccountLockedError):
        await client.get_account_overview()

    # A locked account is terminal: one GET, one POST, no retries.
    assert aioclient_mock.call_count == CALLS_ONE_LOGIN


async def test_wrong_credentials(
    aioclient_mock: AiohttpClientMocker,
    client: ArenaClient,
) -> None:
    """Test account wrong password."""
    aioclient_mock.get(OVERVIEW_URL, text=load_fixture("not_logged_in.html"))
    aioclient_mock.post(
        OVERVIEW_URL,
        params=LOGIN_PARAMS,
        text=load_fixture("login_failed_wrong_credentials.html"),
    )

    with pytest.raises(ArenaInvalidCredentialsError):
        await client.get_account_overview()

    # Wrong credentials are terminal: one GET, one POST, no retries.
    assert aioclient_mock.call_count == CALLS_ONE_LOGIN
