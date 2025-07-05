"""Test the Axiell Arena client."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import aiohttp
from aioresponses import aioresponses
import pytest

from custom_components.folkbibliotek_sverige.axiell_arena_client import (
    ArenaAccountLockedError,
    ArenaClient,
    ArenaInvalidCredentialsError,
    ArenaLoginError,
)

from . import load_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from syrupy import SnapshotAssertion

BASE_URL = "https://folkbiblioteken.lund.se"
USERNAME = "username"
PASSWORD = "password"


@pytest.fixture
async def client() -> AsyncGenerator[ArenaClient]:
    """Return a go2rtc rest client."""
    async with (
        aiohttp.ClientSession() as session,
    ):
        client_ = ArenaClient(
            session=session, url=BASE_URL, username=USERNAME, password=PASSWORD
        )
        yield client_


@pytest.fixture(name="responses")
def aioresponses_fixture() -> Generator[aioresponses]:
    """Return aioresponses fixture."""
    with aioresponses() as mocked_responses:
        yield mocked_responses


async def test_success(
    responses: aioresponses,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful retrieval of account overview."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("logged_in.html"),
    )

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == snapshot
    assert client.get_active_reservations(overview) == []
    assert client.get_ready_reservations(overview) == []


async def test_success_no_loans(
    responses: aioresponses,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful retrieval of account overview with no checked out media."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("logged_in_no_loans.html"),
    )

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == []
    assert client.get_active_reservations(overview) == snapshot
    assert client.get_ready_reservations(overview) == []


async def test_success_no_reservations(
    responses: aioresponses,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful retrieval of account overview with no holds."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("logged_in_no_reservations.html"),
    )

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == snapshot
    assert client.get_active_reservations(overview) == []
    assert client.get_ready_reservations(overview) == []


async def test_success_reservation_to_pick_up(
    responses: aioresponses,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful retrieval of account overview with hold to pick up."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("logged_in_reservation_to_pick_up.html"),
    )

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == snapshot
    assert client.get_active_reservations(overview) == []
    assert client.get_ready_reservations(overview) == snapshot


async def test_success_need_login(
    responses: aioresponses,
    client: ArenaClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test log in."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("not_logged_in.html"),
    )
    escaped_url = re.escape(f"{BASE_URL}/protected/my-account/overview")
    responses.post(
        re.compile(rf"^{escaped_url}\?_patronLogin_WAR.*"),
        body=load_fixture("logged_in.html"),
        repeat=True,
    )

    overview = await client.get_account_overview()
    assert client.get_loans(overview) == snapshot
    assert client.get_active_reservations(overview) == []
    assert client.get_ready_reservations(overview) == []


async def test_no_login(
    responses: aioresponses,
    client: ArenaClient,
) -> None:
    """Test no log in."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("not_logged_in.html"),
    )
    escaped_url = re.escape(f"{BASE_URL}/protected/my-account/overview")
    responses.post(
        re.compile(rf"^{escaped_url}\?_patronLogin_WAR.*"),
        body=load_fixture("not_logged_in.html"),
        repeat=True,
    )

    with pytest.raises(ArenaLoginError):
        await client.get_account_overview()


async def test_account_locked(
    responses: aioresponses,
    client: ArenaClient,
) -> None:
    """Test account is locked."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("not_logged_in.html"),
    )
    escaped_url = re.escape(f"{BASE_URL}/protected/my-account/overview")
    responses.post(
        re.compile(rf"^{escaped_url}\?_patronLogin_WAR.*"),
        body=load_fixture("login_failed_too_many_attempts.html"),
    )

    with pytest.raises(ArenaAccountLockedError):
        await client.get_account_overview()


async def test_wrong_credentials(
    responses: aioresponses,
    client: ArenaClient,
) -> None:
    """Test account wrong password."""
    responses.get(
        f"{BASE_URL}/protected/my-account/overview",
        body=load_fixture("not_logged_in.html"),
    )
    escaped_url = re.escape(f"{BASE_URL}/protected/my-account/overview")
    responses.post(
        re.compile(rf"^{escaped_url}\?_patronLogin_WAR.*"),
        body=load_fixture("login_failed_wrong_credentials.html"),
    )

    with pytest.raises(ArenaInvalidCredentialsError):
        await client.get_account_overview()
