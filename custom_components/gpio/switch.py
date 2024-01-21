"""Allows to configure a switch using GPIO."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_NAME,
    CONF_DEVICE,
    CONF_PORT,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    DEVICE_DEFAULT_NAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, PLATFORMS, DEFAULT_DEVICE, setup_output, write_output

CONF_PULL_MODE = "pull_mode"
CONF_PORTS = "ports"
CONF_INVERT_LOGIC = "invert_logic"

DEFAULT_INVERT_LOGIC = False

_SWITCHES_LEGACY_SCHEMA = vol.Schema({cv.positive_int: cv.string})

_SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PORT): cv.positive_int,
        vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
        vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Exclusive(CONF_PORTS, CONF_SWITCHES): _SWITCHES_LEGACY_SCHEMA,
            vol.Exclusive(CONF_SWITCHES, CONF_SWITCHES): vol.All(
                cv.ensure_list, [_SWITCH_SCHEMA]
            ),
            vol.Optional(CONF_INVERT_LOGIC, default=DEFAULT_INVERT_LOGIC): cv.boolean,
        },
    ),
    cv.has_at_least_one_key(CONF_PORTS, CONF_SWITCHES),
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    setup_reload_service(hass, DOMAIN, PLATFORMS)
    
    switches_conf = config.get(CONF_SWITCHES)
    if switches_conf is not None:
        switches = [GPIOSwitch(switch[CONF_NAME],
                               switch[CONF_DEVICE],
                               switch[CONF_PORT],
                               switch[CONF_INVERT_LOGIC],
                               switch.get(CONF_UNIQUE_ID))
                    for switch in switches_conf]
    else:
        # Legacy schema
        switches = [GPIOSwitch(name, DEFAULT_DEVICE, port, config[CONF_INVERT_LOGIC])
                    for port, name in config[CONF_PORTS].items()]
        
    add_entities(switches, update_before_add=True)


class GPIOSwitch(SwitchEntity):
    """A switch that takes its state from a port on a GPIO device."""

    def __init__(self, name, device, port, invert_logic, unique_id=None):
        self._attr_name = name or DEVICE_DEFAULT_NAME
        self._attr_unique_id = unique_id
        self._attr_should_poll = False
        self._invert_logic = invert_logic
        self._state = False
        self._line = setup_output(device, port)
        write_output(self._line, 1 if self._invert_logic else 0)

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        self._line.release()
        self._line = None

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        write_output(self._line, 0 if self._invert_logic else 1)
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        write_output(self._line, 1 if self._invert_logic else 0)
        self._state = False
        self.schedule_update_ha_state()
