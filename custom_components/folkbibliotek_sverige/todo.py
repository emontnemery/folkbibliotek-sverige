"""Todo platform for Folkbibliotek Sverige."""

from __future__ import annotations

from abc import abstractmethod
import datetime
from typing import TYPE_CHECKING

from homeassistant.components.todo import TodoItem, TodoItemStatus, TodoListEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import FolkbibliotekSverigeDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from . import FolkbibliotekSverigeConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: FolkbibliotekSverigeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Todoist todo platform config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            FolkbibliotekSverigeCheckedOut(
                coordinator, entry.entry_id, entry.data["name"]
            ),
            FolkbibliotekSverigeHolds(coordinator, entry.entry_id, entry.data["name"]),
        ]
    )


class FolkbibliotekSverigeTodoListEntity(
    CoordinatorEntity[FolkbibliotekSverigeDataUpdateCoordinator], TodoListEntity
):
    """A Todoist TodoListEntity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FolkbibliotekSverigeDataUpdateCoordinator,
        config_entry_id: str,
        config_entry_name: str,
    ) -> None:
        """Initialize TodoistTodoListEntity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = f"{config_entry_id}-{self._attr_translation_key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, config_entry_id)},
            name=config_entry_name,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Data: %s", self.coordinator.data)
        if self.coordinator.data is None:
            self._attr_todo_items = None
        else:
            self._attr_todo_items = self._get_todo_items()
        LOGGER.debug("TODO-items: %s", self._attr_todo_items)
        super()._handle_coordinator_update()

    @abstractmethod
    def _get_todo_items(self) -> list[TodoItem]:
        """Get the todo items for this entity."""
        # This method is abstract and should be implemented in subclasses

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass update state from existing coordinator data."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class FolkbibliotekSverigeCheckedOut(FolkbibliotekSverigeTodoListEntity):
    """Checked out items."""

    _attr_translation_key = "checked_out"

    def __init__(
        self,
        coordinator: FolkbibliotekSverigeDataUpdateCoordinator,
        config_entry_id: str,
        config_entry_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator=coordinator,
            config_entry_id=config_entry_id,
            config_entry_name=config_entry_name,
        )

    def _get_todo_items(self) -> list[TodoItem]:
        """Get the todo items for this entity."""
        return [
            TodoItem(
                summary=loan.title,
                uid=f"{loan.record_id}",
                status=TodoItemStatus.NEEDS_ACTION,
                due=datetime.date.fromisoformat(loan.expire_date),
                description="Can be renewed"
                if loan.renewable
                else "Can not be renewed",  # Should we include more details?
            )
            for loan in self.coordinator.data.loans
        ]


class FolkbibliotekSverigeHolds(FolkbibliotekSverigeTodoListEntity):
    """Holds."""

    _attr_translation_key = "holds"

    def __init__(
        self,
        coordinator: FolkbibliotekSverigeDataUpdateCoordinator,
        config_entry_id: str,
        config_entry_name: str,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator=coordinator,
            config_entry_id=config_entry_id,
            config_entry_name=config_entry_name,
        )

    def _get_todo_items(self) -> list[TodoItem]:
        """Get the todo items for this entity."""
        items = [
            TodoItem(
                summary=reservation.title,
                uid=f"{reservation.record_id}",
                status=None,
                description=f"Queue number {reservation.queue_number}",
            )
            for reservation in self.coordinator.data.active_reservations
        ]
        items.extend(
            TodoItem(
                summary=reservation.title,
                uid=f"{reservation.record_id}",
                status=TodoItemStatus.NEEDS_ACTION,
                due=datetime.date.fromisoformat(reservation.pickup_date),
                description=f"Ready for pickup at {reservation.pickup_library}",
            )
            for reservation in self.coordinator.data.waiting_reservations
        )
        return items
