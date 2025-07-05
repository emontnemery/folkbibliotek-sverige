"""Python client for Axiell Arena."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Self

from bs4 import BeautifulSoup, NavigableString, Tag

if TYPE_CHECKING:
    import aiohttp

_LOGGER = logging.getLogger(__name__)

LOGIN_ATTEMPTS = 3


class ArenaError(Exception):
    """Base class for exceptions in this module."""


class ArenaLoginError(ArenaError):
    """Exception raised for errors in the login process."""

    msg = "Could not log in"

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(self.msg)


class ArenaLoginFormNotFoundError(ArenaLoginError):
    """Exception raised when the login form is not found."""

    msg = "Could not find login form"


class ArenaAccountLockedError(ArenaLoginError):
    """Exception raised when the account is locked."""

    msg = "Account is locked"


class ArenaInvalidCredentialsError(ArenaLoginError):
    """Exception raised when the credentials are not valid."""

    msg = "Invalid credentials"


class ArenaNotLoggedInError(ArenaError):
    """Exception raised when not logged in."""

    msg = "Not logged in"


def _get_value(tag: Tag, selector: str) -> str | None:
    selected = tag.select_one(f"{selector}  span.arena-value")
    if not selected:
        return None
    return selected.text


@dataclass
class LibraryMaterial:
    """Library material container."""

    record_id: str | None = None
    type: str | None = None
    title: str | None = None
    author: str | None = None
    year: str | None = None


@dataclass
class LibraryLoan(LibraryMaterial):
    """Library loan container."""

    loan_date: str | None = None
    expire_date: str | None = None
    renewable: bool | None = None

    @classmethod
    def from_soup(cls, soup: Tag) -> Self:
        """Construct a library loan from a BeautifulSoup tag."""
        renewable = False
        if "arena-renewal-false" in soup.get("class"):
            renewable = False
        elif "arena-renewal-true" in soup.get("class"):
            renewable = True
        return cls(
            record_id=soup.select_one("span.arena-record-id").text,
            type=_get_value(soup, "div.arena-record-media"),
            title=soup.select_one("div.arena-record-title span").text,
            author=_get_value(soup, "div.arena-record-author"),
            year=_get_value(soup, "div.arena-record-year"),
            loan_date=_get_value(soup, "div.arena-renewal-branch").rsplit(" ", 1)[-1],
            expire_date=soup.select_one("span.arena-renewal-date-value").text,
            renewable=renewable,
        )


@dataclass
class LibraryReservation(LibraryMaterial):
    """Library reservation container."""

    created_date: str | None = None
    expire_date: str | None = None
    queue_number: str | None = None
    pickup_library: str | None = None

    @classmethod
    def from_soup(cls, soup: Tag) -> Self:
        """Construct a library reservation from a BeautifulSoup tag."""
        return cls(
            record_id=soup.select_one("span.arena-record-id").text,
            type=_get_value(soup, "div.arena-record-media"),
            title=soup.select_one("div.arena-record-title span").text,
            author=_get_value(soup, "div.arena-record-author"),
            year=_get_value(soup, "div.arena-record-year"),
            created_date=_get_value(soup, "td.arena-reservation-from-container"),
            expire_date=_get_value(soup, "td.arena-reservation-to-container"),
            queue_number=_get_value(soup, "td.arena-record-queue").split(" ")[0],
            pickup_library=_get_value(soup, "td.arena-record-branch"),
        )


@dataclass
class LibraryReservationReady(LibraryMaterial):
    """Library reservation ready container."""

    created_date: str | None = None
    pickup_date: str | None = None
    reservation_number: str | None = None
    pickup_library: str | None = None

    @classmethod
    def from_soup(cls, soup: Tag) -> Self:
        """Construct a library reservation from a BeautifulSoup tag."""
        return cls(
            record_id=soup.select_one("span.arena-record-id").text,
            type=_get_value(soup, "div.arena-record-media"),
            title=soup.select_one("div.arena-record-title span").text,
            author=_get_value(soup, "div.arena-record-author"),
            year=_get_value(soup, "div.arena-record-year"),
            created_date=_get_value(soup, "td.arena-reservation-from-container"),
            pickup_date=_get_value(soup, "td.arena-record-expire"),
            reservation_number=_get_value(soup, "td.arena-record-pickup"),
            pickup_library=_get_value(soup, "td.arena-record-branch"),
        )


@dataclass
class LibraryDebt(LibraryMaterial):
    """Library debt container."""

    fee_date: str | None = None
    fee_type: str | None = None
    fee_amount: str | None = None


class ArenaClient:
    """Axiell Arena client."""

    def __init__(
        self, *, session: aiohttp.ClientSession, url: str, username: str, password: str
    ) -> None:
        """Initialize the client."""
        self.session = session
        self.base_url = url
        self.username = username
        self.password = password

    async def get_account_overview_html(self) -> BeautifulSoup:
        """Get the account overview."""
        url = f"{self.base_url}/protected/my-account/overview"
        return await self._get_url(url)

    async def get_account_overview(self) -> BeautifulSoup:
        """Get the account overview and wrap it in a BeautifulSoup object."""
        return BeautifulSoup(await self.get_account_overview_html(), "html.parser")

    def get_loans(self, soup: BeautifulSoup) -> list[LibraryLoan]:
        """Get library loans."""
        table: Tag = soup.select_one("table#loansTable")
        if not table:
            return []
        _LOGGER.debug("Loans: %s", table)
        return [
            LibraryLoan.from_soup(row)
            for row in table.children
            if not isinstance(row, NavigableString) and row.name == "tr"
        ]

    def _get_reservations(self, soup: BeautifulSoup) -> Tag | None:
        reservations = soup.select_one("div.portlet-myReservations")
        if not reservations or not reservations.select("div.arena-library-record"):
            _LOGGER.debug("No reservations")
            return None
        _LOGGER.debug("Reservations: %s", reservations)
        return reservations

    def get_active_reservations(self, soup: BeautifulSoup) -> list[LibraryReservation]:
        """Get library reservations."""
        if not (reservations := self._get_reservations(soup)):
            return []
        return [
            LibraryReservation.from_soup(reservation)
            for reservation in reservations.select("div.arena-library-record")
            if not reservation.select_one("td.arena-record-pickup")
        ]

    def get_ready_reservations(
        self, soup: BeautifulSoup
    ) -> list[LibraryReservationReady]:
        """Get library reservations."""
        if not (reservations := self._get_reservations(soup)):
            return []
        return [
            LibraryReservationReady.from_soup(reservation)
            for reservation in reservations.select("div.arena-library-record")
            if reservation.select_one("td.arena-record-pickup")
        ]

    async def _get_url(self, url: str) -> str:
        try:
            async with self.session.get(url) as resp:
                resp.raise_for_status()
                text = await resp.text()
                self._raise_if_not_logged_in(text)
                return text
        except ArenaNotLoggedInError:
            return await self._login_and_get_url(url)

    async def _login_and_get_url(self, url: str) -> str:
        query_params = {
            "p_p_id": "patronLogin_WAR_arenaportlet",
            "p_p_lifecycle": 1,
            "p_p_state": "normal",
            "p_p_mode": "view",
            "_patronLogin_WAR_arenaportlet__wu": (
                "/patronLogin/?wicket:interface=:1:signInPanel:signInFormPanel"
                ":signInForm::IFormSubmitListener::"
            ),
        }
        form_data = {
            "id__patronLogin__WAR__arenaportlet____3_hf_0": "",
            "openTextUsernameContainer:openTextUsername": self.username,
            "textPassword": self.password,
        }
        self.session.cookie_jar.clear()

        attempt = 0
        while attempt < LOGIN_ATTEMPTS:
            attempt += 1
            _LOGGER.debug("Attempting to log in, attempt %d", attempt)
            async with self.session.post(
                url, params=query_params, data=form_data
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                try:
                    self._raise_if_not_logged_in(text)
                except ArenaNotLoggedInError:
                    continue
                return text
        raise ArenaLoginError("Unknown login error")  # noqa: TRY003, EM101

    def _raise_if_not_logged_in(self, text: str) -> None:
        soup = BeautifulSoup(text, "html.parser")
        if not (
            patron_login := soup.find(
                "div", {"id": "portlet_patronLogin_WAR_arenaportlet"}
            )
        ):
            raise ArenaLoginFormNotFoundError
        if not (patron_login.find("div", {"class": "arena-patron-form"})):
            _LOGGER.debug("Logged in")
            return
        if not (
            feedback_panel := patron_login.find(
                "span", {"class": "feedbackPanelWARNING"}
            )
        ):
            _LOGGER.debug("No feedback panel found: %s", text)
            raise ArenaNotLoggedInError("No feedback panel found: %s", text)  # noqa: TRY003, EM101
        if feedback_panel.text.startswith("Ditt konto har stängts"):
            _LOGGER.debug("Account locked")
            raise ArenaAccountLockedError
        if feedback_panel.text.startswith("Du blev inte inloggad"):
            _LOGGER.debug("Invalid credentials")
            raise ArenaInvalidCredentialsError
        _LOGGER.debug("Unknown error while logging in: %s", feedback_panel.text)
        raise ArenaNotLoggedInError(feedback_panel.text)
