"""Binary sensor platform for Moscow PGU component

This file is yet to be used."""

__all__ = (
    "BASE_CLASS",
    "async_setup_entry",
    "MoscowPGUBinarySensor",
)

from abc import ABC
from typing import Final

from homeassistant.components.binary_sensor import BinarySensorEntity

from custom_components.moscow_pgu._base import MoscowPGUEntity, make_platform_setup


class MoscowPGUBinarySensor(MoscowPGUEntity, BinarySensorEntity, ABC):
    """Base for Moscow PGU binary sensors"""


BASE_CLASS: Final = MoscowPGUBinarySensor
async_setup_entry: Final = make_platform_setup(*BASE_CLASS.__subclasses__())
