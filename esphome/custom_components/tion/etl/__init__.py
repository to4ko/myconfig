# Dummy integration to allow relying on ETL
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.core import coroutine_with_priority

CODEOWNERS = ["@dentra"]

CONFIG_SCHEMA = cv.Schema({})


@coroutine_with_priority(200.0)
async def to_code(config):
    # Pinned "20.35.8" via the PlatformIO/ESP registry is no longer resolvable
    # on current ESPHome (2026.x moved esp-idf lib resolution through a
    # registry lookup that no longer serves this old version pin). Pull ETL
    # straight from its GitHub source instead, matching upstream's current
    # dentra/esphome-components master and sidestepping registry resolution
    # entirely (ESPHome treats a git URL as a direct source, no version
    # lookup involved).
    cg.add_library("Embedded Template Library", None, "https://github.com/ETLCPP/etl")
