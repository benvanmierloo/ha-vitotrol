"""Datetime platform for the Viessmann Vitotrol integration."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VitotrolConfigEntry
from .api import AttributeTypeInfo, VitotrolDevice
from .attributes import ATTRIBUTE_REGISTRY, AttrMeta
from .coordinator import VitotrolCoordinator
from .entity import VitotrolEntity, infer_unknown_metadata

_LOGGER = logging.getLogger(__name__)

# API date/time string formats, tried in order
_PARSE_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%d.%m.%Y",
)
_WRITE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_api_datetime(raw: str) -> datetime | None:
    """Parse an API date string into an aware UTC datetime."""
    for fmt in _PARSE_FORMATS:
        try:
            naive = datetime.strptime(raw.strip(), fmt)
            return naive.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    _LOGGER.debug("Cannot parse datetime string %r", raw)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VitotrolConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Vitotrol datetime entities."""
    runtime = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[DateTimeEntity] = []

    for device in coordinator.devices:
        catalog = coordinator.get_attribute_catalog(device.device_id)

        for attr_id, info in catalog.items():
            meta = ATTRIBUTE_REGISTRY.get(attr_id)

            if meta is not None:
                if meta.platform != "datetime":
                    continue
                entities.append(VitotrolDateTime(coordinator, device, info, meta))
            else:
                inferred = infer_unknown_metadata(info)
                if inferred.platform != "datetime":
                    continue
                entities.append(VitotrolDateTime(coordinator, device, info, meta=None))

    async_add_entities(entities)


class VitotrolDateTime(VitotrolEntity, DateTimeEntity):
    """Datetime entity for a Vitotrol date attribute."""

    def __init__(
        self,
        coordinator: VitotrolCoordinator,
        device: VitotrolDevice,
        info: AttributeTypeInfo,
        meta: AttrMeta | None,
    ) -> None:
        key = meta.name.lower().replace(" ", "_") if meta else f"attr_{info.attr_id}"
        super().__init__(coordinator, device, key)
        self._vitotrol_attr_id = info.attr_id

        if meta is not None:
            self._attr_name = meta.name
            self._attr_entity_registry_enabled_default = meta.enabled_by_default
        else:
            inferred = infer_unknown_metadata(info)
            self._attr_name = inferred.display_name
            self._attr_entity_registry_enabled_default = False

    @property
    def available(self) -> bool:
        """Return True if the attribute is present in the data."""
        return super().available and self._vitotrol_attr_id in self._device_data

    @property
    def native_value(self) -> datetime | None:
        """Return the current datetime value."""
        raw = self._get_attr_value(self._vitotrol_attr_id)
        if raw is None:
            return None
        return _parse_api_datetime(raw)

    async def async_set_value(self, value: datetime) -> None:
        """Set a new datetime value."""
        str_value = value.astimezone(timezone.utc).strftime(_WRITE_FORMAT)
        await self.coordinator.async_write(
            self._device, self._vitotrol_attr_id, str_value
        )
        self._update_coordinator_data(self._vitotrol_attr_id, str_value)
        self.async_write_ha_state()
