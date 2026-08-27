import esphome.codegen as cg
import esphome.config_validation as cv
from esphome import core
from esphome.components import ble_client, uart
from esphome.const import CONF_ID
from esphome.cpp_generator import MockObjClass

AUTO_LOAD = ["etl"]

IS_PLATFORM_COMPONENT = True

CONF_VPORT_ID = "vport_id"
CONF_VPORT_IO_ID = "vport_io_id"
CONF_PERSISTENT_CONNECTION = "persistent_connection"
CONF_DISABLE_SCAN = "disable_scan"
CONF_COMMAND_INTERVAL = "command_interval"
CONF_COMMAND_QUEUE_SIZE = "command_queue_size"
CONF_CONNECTION_TIMEOUT = "connection_timeout"

vport_ns = cg.esphome_ns.namespace("vport")
VPort = vport_ns.class_("VPort")

VPORT_CLIENT_SCHEMA = cv.Schema(
    {
        cv.GenerateID(CONF_VPORT_ID): cv.use_id(VPort),
    }
)


# def _add_command_queue_size(config):
#     var: core.ID = config[CONF_ID]
#     var.type = var.type.template(config[CONF_COMMAND_QUEUE_SIZE])
#     return config


def vport_schema(
    vport_class: MockObjClass,
    io_class: MockObjClass,
    default_update_interval=None,
    default_command_interval="100ms",
):
    if not vport_class.inherits_from(VPort):
        raise cv.Invalid("Not a VPort Component")
    schema = cv.Schema(
        {
            cv.GenerateID(): cv.declare_id(vport_class),
            cv.GenerateID(CONF_VPORT_IO_ID): cv.declare_id(io_class),
            cv.Optional(
                CONF_COMMAND_INTERVAL, default=default_command_interval
            ): cv.update_interval,
            cv.Optional(CONF_COMMAND_QUEUE_SIZE, default=16): cv.int_range(2, 100),
            cv.Optional(CONF_CONNECTION_TIMEOUT): cv.positive_time_period_milliseconds,
        }
    )
    # schema = schema.add_extra(_add_command_queue_size)
    if default_update_interval is None:
        schema = schema.extend(cv.COMPONENT_SCHEMA)
    else:
        schema = schema.extend(cv.polling_component_schema(default_update_interval))
    return schema


def vport_ble_schema(
    vport_class: MockObjClass,
    io_class: MockObjClass,
    default_update_interval=None,
):
    return (
        vport_schema(vport_class, io_class, default_update_interval)
        .extend(ble_client.BLE_CLIENT_SCHEMA)
        .extend(
            {
                cv.Optional(CONF_PERSISTENT_CONNECTION, default=False): cv.boolean,
                cv.Optional(CONF_DISABLE_SCAN, default=False): cv.boolean,
            }
        )
    )


def vport_uart_schema(
    vport_class: MockObjClass,
    io_class: MockObjClass,
    default_update_interval=None,
):
    return vport_schema(vport_class, io_class, default_update_interval, "20ms").extend(
        uart.UART_DEVICE_SCHEMA
    )


def _find_by_id(platform: str, find_id) -> core.ID:
    for _, item in enumerate(core.CORE.config[platform]):
        item_id: core.ID = item["id"]
        if str(item_id.id) == str(find_id):
            return item_id
    return None


def vport_find_by_id(find_id):
    return _find_by_id("vport", find_id)


def vport_find(config):
    return vport_find_by_id(config[CONF_VPORT_ID])


async def vport_get_var(config):
    return await cg.get_variable(config[CONF_VPORT_ID])


async def _setup_vport_core(config, vio):
    var = cg.new_Pvariable(config[CONF_ID], vio)
    await cg.register_component(var, config)

    cg.add(var.set_command_interval(config[CONF_COMMAND_INTERVAL]))
    # FIXME queue size configured for all components, but not concrete
    cg.add_define("USE_VPORT_COMMAND_QUEUE_SIZE", config[CONF_COMMAND_QUEUE_SIZE])

    return var


async def setup_vport_ble(config):
    vio = cg.new_Pvariable(config[CONF_VPORT_IO_ID])
    await ble_client.register_ble_node(vio, config)

    var = await _setup_vport_core(config, vio)

    if value := config.get(CONF_PERSISTENT_CONNECTION, False):
        cg.add(var.set_persistent_connection(value))

    # FIXME reimplement and add again
    # cg.add(var.set_disable_scan(config[CONF_DISABLE_SCAN]))

    if value := config.get(CONF_CONNECTION_TIMEOUT, 0):
        cg.add(var.set_connection_timeout(value))

    cg.add_define("USE_VPORT_BLE")

    return var


async def setup_vport_uart(config):
    urt = await cg.get_variable(config[uart.CONF_UART_ID])
    vio = cg.new_Pvariable(config[CONF_VPORT_IO_ID], urt)

    var = await _setup_vport_core(config, vio)

    cg.add_define("USE_VPORT_UART")

    return var


# async def to_code(config):
#     # FIXME remove due to add_define in setup
#     if "uart" in core.CORE.config:
#         cg.add_build_flag("-DUSE_VPORT_UART")
#     if "ble_client" in core.CORE.config:
#         cg.add_build_flag("-DUSE_VPORT_BLE")
