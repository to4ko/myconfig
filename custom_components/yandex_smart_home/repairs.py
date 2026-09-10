"""Repairs for the Yandex Smart Home."""

from typing import TYPE_CHECKING, cast

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er, issue_registry as ir, label_registry as lr
from homeassistant.helpers.entityfilter import CONF_INCLUDE_ENTITIES
from homeassistant.helpers.selector import BooleanSelector
import voluptuous as vol

from . import DOMAIN
from .const import CONF_ADD_LABEL, CONF_FILTER, CONF_LABEL, ISSUE_ID_PREFIX_UNEXPOSED_ENTITY_FOUND, EntityFilterSource
from .entry_data import ConfigEntryData

if TYPE_CHECKING:
    from . import YandexSmartHome


class EmptyRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow without any side effects."""

    async def async_step_init(self, _: dict[str, str] | None = None) -> FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_create_entry(data={})


class UnexposedEntityFoundConfigEntryRepairFlow(RepairsFlow):
    """Handler for an "unexposed entity found" issue fixing flow."""

    def __init__(self, entry_data: ConfigEntryData) -> None:
        """Initialize the flow."""
        self._entry_data = entry_data

    async def async_step_init(self, _: dict[str, str] | None = None) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            if user_input[CONF_INCLUDE_ENTITIES]:
                entry = self._entry_data.entry
                options = entry.options.copy()
                options[CONF_FILTER] = {
                    CONF_INCLUDE_ENTITIES: sorted(
                        set(entry.options[CONF_FILTER][CONF_INCLUDE_ENTITIES]) | self._entry_data.unexposed_entities
                    )
                }
                self.hass.config_entries.async_update_entry(entry, options=options)

            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({vol.Required(CONF_INCLUDE_ENTITIES): BooleanSelector()}),
        )


class UnexposedEntityFoundLabelRepairFlow(RepairsFlow):
    """Handler for an "unexposed entity found" issue fixing flow."""

    def __init__(self, entry_data: ConfigEntryData) -> None:
        """Initialize the flow."""
        self._entry_data = entry_data

    async def async_step_init(self, _: dict[str, str] | None = None) -> FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> FlowResult:
        """Handle the confirm step of a fix flow."""
        label = self._entry_data.entry.options[CONF_LABEL]
        label_entry = lr.async_get(self.hass).async_get_label(label)

        if user_input is not None:
            if user_input[CONF_ADD_LABEL]:
                registry = er.async_get(self.hass)
                for entity_id in self._entry_data.unexposed_entities:
                    if entity := registry.async_get(entity_id):
                        registry.async_update_entity(
                            entity.entity_id,
                            labels=entity.labels | {label},
                        )

            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({vol.Required(CONF_ADD_LABEL): BooleanSelector()}),
            description_placeholders={CONF_LABEL: label_entry.name if label_entry else label},
        )


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Create flow."""
    assert data is not None
    entry = hass.config_entries.async_get_entry(cast(str, data["entry_id"]))
    if not entry or DOMAIN not in hass.data:
        return EmptyRepairFlow()

    component: YandexSmartHome = hass.data[DOMAIN]
    try:
        entry_data = component.get_entry_data(entry)
    except KeyError:
        return EmptyRepairFlow()

    if issue_id == ISSUE_ID_PREFIX_UNEXPOSED_ENTITY_FOUND + EntityFilterSource.CONFIG_ENTRY:
        return UnexposedEntityFoundConfigEntryRepairFlow(entry_data)

    if issue_id == ISSUE_ID_PREFIX_UNEXPOSED_ENTITY_FOUND + EntityFilterSource.LABEL:
        return UnexposedEntityFoundLabelRepairFlow(entry_data)

    raise NotImplementedError


def delete_unexposed_entity_found_issues(hass: HomeAssistant) -> None:
    """Delete repair issues for an unexposed entity."""
    for filter_source in EntityFilterSource:
        ir.async_delete_issue(hass, DOMAIN, ISSUE_ID_PREFIX_UNEXPOSED_ENTITY_FOUND + filter_source)
