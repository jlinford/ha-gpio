"""Support for binary sensor using GPIO."""
from __future__ import annotations

import datetime

import voluptuous as vol

from homeassistant.components.binary_sensor import PLATFORM_SCHEMA, BinarySensorEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICE,
    CONF_PORT,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    DEVICE_DEFAULT_NAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.event import async_track_time_interval

from . import DOMAIN, PLATFORMS, DEFAULT_DEVICE, enable_edge_detect, read_edge_events, read_input, setup_input


CONF_BOUNCETIME = "bouncetime"
CONF_INVERT_LOGIC = "invert_logic"
CONF_PORTS = "ports"
CONF_PULL_MODE = "pull_mode"

DEFAULT_BOUNCETIME = 50
DEFAULT_INVERT_LOGIC = False
DEFAULT_PULL_MODE = "UP"

_SENSORS_LEGACY_SCHEMA = vol.Schema({cv.positive_int: cv.string})

_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PORT): cv.positive_int,
        vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
        vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): cv.string,
        vol.Optional(CONF_BOUNCETIME, default=DEFAULT_BOUNCETIME): cv.positive_int,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Exclusive(CONF_PORTS, CONF_SENSORS): _SENSORS_LEGACY_SCHEMA,
            vol.Exclusive(CONF_SENSORS, CONF_SENSORS): vol.All(
                cv.ensure_list, [_SENSOR_SCHEMA]
            ),
            vol.Optional(CONF_BOUNCETIME, default=DEFAULT_BOUNCETIME): cv.positive_int,
            vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
            vol.Optional(CONF_PULL_MODE, default=DEFAULT_PULL_MODE): cv.string,
            vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
        },
    ),
    cv.has_at_least_one_key(CONF_PORTS, CONF_SENSORS),
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    setup_reload_service(hass, DOMAIN, PLATFORMS)

    sensors_conf = config.get(CONF_SENSORS)
    if sensors_conf is not None:
        sensors = [GPIOBinarySensor(sensor[CONF_NAME],
                                    sensor[CONF_DEVICE],
                                    sensor[CONF_PORT],
                                    sensor[CONF_PULL_MODE],
                                    sensor[CONF_BOUNCETIME],
                                    sensor[CONF_INVERT_LOGIC],
                                    sensor.get(CONF_UNIQUE_ID))
                   for sensor in sensors_conf]
    else:
        # Legacy schema
        sensors = [GPIOBinarySensor(port_name, 
                                    DEFAULT_DEVICE, 
                                    port_num, 
                                    config[CONF_PULL_MODE], 
                                    config[CONF_BOUNCETIME], 
                                    config[CONF_INVERT_LOGIC])
                   for port_num, port_name in config[CONF_PORTS].items()]
        
    add_entities(sensors, update_before_add=True)



class GPIOBinarySensor(BinarySensorEntity):
    """A binary sensor that takes its state from a port on a GPIO device."""

    def __init__(self, name, device, port, pull_mode, bouncetime, invert_logic, unique_id=None):
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_unique_id = unique_id
        self._bouncetime = bouncetime
        self._invert_logic = invert_logic
        self._state = None
        # Disable HA polling of this entity to avoid unnecessary updates to HA state.
        # Poll the GPIO port and update HA state when an edge event is detected.
        self._attr_should_poll = False
        self._line = setup_input(device, port, pull_mode)
        enable_edge_detect(self._line, "BOTH", self._bouncetime)

    async def _detect_edges(self, time=None):
        if read_edge_events(self._line, timeout=0):
            self.async_schedule_update_ha_state(force_refresh=True)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        async_track_time_interval(
            self.hass, 
            self._detect_edges, 
            datetime.timedelta(milliseconds=self._bouncetime),
            cancel_on_shutdown=True)

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        self._line.release()
        self._line = None

    @property
    def is_on(self):
        return self._state != self._invert_logic

    def update(self):
        self._state = read_input(self._line)
