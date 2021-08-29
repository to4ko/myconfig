from abc import ABC
from typing import Any, ClassVar, Dict, List, Optional, SupportsFloat, Tuple, Union

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TIME
from homeassistant.helpers import config_validation as cv
from homeassistant.util.dt import now as dt_now

from custom_components.moscow_pgu._base import MoscowPGUEntity
from custom_components.moscow_pgu.const import (
    ATTR_DRY_RUN,
    ATTR_FORCE,
    ATTR_INDICATIONS,
    ATTR_ORIGINAL_INDICATIONS,
    ATTR_REASON,
    ATTR_SERVICE_TYPE,
    ATTR_SUCCESS,
    DEVICE_CLASS_PGU_INDICATIONS,
    EVENT_FORMAT_INDICATIONS_PUSH,
    TYPE_ELECTRIC,
    TYPE_WATER,
)

INDICATIONS_VALIDATOR = vol.Any(
    vol.All(cv.positive_float, lambda x: [x]),
    vol.All(cv.ensure_list, vol.Length(min=1), [cv.positive_float]),
    vol.All(
        cv.string,
        vol.Length(min=1),
        lambda x: list(map(str.strip, x.split(","))),
        vol.Any([cv.positive_float], [cv.entity_id]),
    ),
)
SERVICE_PUSH_INDICATIONS = "push_indications"
SERVICE_PUSH_INDICATIONS_SCHEMA = {
    vol.Required(ATTR_INDICATIONS): INDICATIONS_VALIDATOR,
    vol.Optional(ATTR_FORCE, default=False): cv.boolean,
    vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean,
    vol.Optional(ATTR_SERVICE_TYPE): vol.All(
        cv.string, vol.Lower, vol.In((TYPE_ELECTRIC, TYPE_WATER))
    ),
}


class MoscowPGUSubmittableEntity(MoscowPGUEntity, ABC):
    service_type: ClassVar[Union[str, Tuple[str, ...]]] = NotImplemented

    @property
    def device_class(self) -> Optional[str]:
        return DEVICE_CLASS_PGU_INDICATIONS

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Register indication pushing service
        self.platform.async_register_entity_service(
            SERVICE_PUSH_INDICATIONS,
            SERVICE_PUSH_INDICATIONS_SCHEMA,
            "async_push_indications",
        )

    async def async_push_indications(
        self,
        indications: List[Union[str, SupportsFloat]],
        force: bool = False,
        service_type: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        error = None
        pass_indications = None
        try:
            if isinstance(self.service_type, str):
                if service_type is None:
                    service_type = self.service_type
                elif service_type != self.service_type:
                    raise ValueError(
                        'Incorrect service type provided (expected: "%s", got: "%s"'
                        % (self.service_type, service_type)
                    )
            elif service_type is None:
                raise ValueError(
                    "Service type not defined for multi-service-type indications entity"
                )
            elif service_type not in self.service_type:
                raise ValueError(
                    'Incorrect service type provided (expected: %s, got: "%s")'
                    % (self.service_type, service_type)
                )

            if not indications:
                raise ValueError("Indications are empty")

            indications_count = await self.async_get_indications_count(service_type, force)
            if indications_count is not None:
                if isinstance(indications_count, int):
                    if indications_count != len(indications):
                        raise ValueError(
                            "Invalid indications count provided (expected: %d, got: %d)"
                            % (indications_count, len(indications))
                        )
                elif len(indications) not in range(indications_count[0], indications_count[1] + 1):
                    raise ValueError(
                        "Invalid indications count provided (expected: %d <= N <= %d, got: %d)"
                        % (indications_count[0], indications_count[1], len(indications))
                    )

            pass_indications = []
            state_machine = self.hass.states
            for indication in indications:
                if isinstance(indication, str):
                    state = state_machine.get(indication)
                    if state is None:
                        raise ValueError(
                            'Could not retrieve state for entity with ID "%s"' % (indication,)
                        )

                    indication = state.state

                pass_indications.append(
                    float(indication)
                )  # will raise ValueError if non-floatable type

            await self._async_push_indications(pass_indications, force, service_type, dry_run)

        except Exception as e:
            error = e
            raise

        finally:
            event_data_dict = {
                ATTR_TIME: dt_now().isoformat(),
                ATTR_ENTITY_ID: self.entity_id,
                ATTR_SERVICE_TYPE: service_type,
                ATTR_INDICATIONS: pass_indications,
                ATTR_ORIGINAL_INDICATIONS: indications,
                ATTR_DRY_RUN: dry_run,
                ATTR_SUCCESS: not error,
            }

            if error:
                event_data_dict[ATTR_REASON] = str(error)

            update_dict = await self.async_get_indications_event_data_dict(
                indications=pass_indications or indications, force=force, service_type=service_type
            )

            if update_dict:
                event_data_dict.update(update_dict)

            self.hass.bus.async_fire(
                event_type=EVENT_FORMAT_INDICATIONS_PUSH % (service_type,),
                event_data=event_data_dict,
            )

    async def async_get_indications_event_data_dict(
        self, indications: List[Union[str, SupportsFloat]], force: bool, service_type: str
    ) -> Dict[str, Any]:
        raise NotImplementedError

    async def async_get_indications_count(
        self, service_type: str, force: bool
    ) -> Optional[Union[int, Tuple[int, int]]]:
        raise NotImplementedError

    async def _async_push_indications(
        self, indications: List[float], force: bool, service_type: str, dry_run: bool
    ) -> None:
        raise NotImplementedError
