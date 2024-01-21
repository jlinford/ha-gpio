"""Support for controlling GPIO pins of a Raspberry Pi."""


import datetime
import gpiod


from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "rpi_gpio"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SWITCH,
]

_CHIP_PATH = "/dev/gpiochip4"
_REQUESTS = {}


def _configure_line(line, **kwargs):
    config = {line: gpiod.LineSettings(**kwargs)}
    try:
        req = _REQUESTS[line]
    except KeyError:
        _REQUESTS[line] = gpiod.request_lines(_CHIP_PATH, consumer=DOMAIN, config=config)
    else:
        req.reconfigure_lines(config=config)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Raspberry PI GPIO component."""
    
    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        for request in _REQUESTS.values():
            request.release()
        _REQUESTS.clear()

    def prepare_gpio(event):
        """Stuff to do when Home Assistant starts."""

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)
    return True


def setup_output(port):
    """Set up a GPIO as output."""
    _configure_line(port, direction=gpiod.line.Direction.OUTPUT)


def setup_input(port, pull_mode):
    """Set up a GPIO as input."""
    _configure_line(
        port, 
        direction=gpiod.line.Direction.INPUT,
        bias=(gpiod.line.Bias.PULL_DOWN if pull_mode == "DOWN" else gpiod.line.Bias.PULL_UP))


def setup_edge_detect(port, debounce_ms):
    """Add detection for RISING and FALLING events."""
    _configure_line(
        port,
        edge_detection=gpiod.line.Edge.BOTH,
        bias=gpiod.line.Bias.PULL_UP,
        debounce_period=datetime.timedelta(milliseconds=debounce_ms))


def write_output(port, value):
    """Write a value to a GPIO."""
    if port in _REQUESTS:
        _REQUESTS[port].set_value(port, gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE)


def read_input(port):
    """Read a value from a GPIO."""
    try:
        req = _REQUESTS[port]
    except KeyError:
        return None
    else:
        return (req.get_value(port) == gpiod.line.Value.ACTIVE)


def read_edge_events(port, timeout):
    """
    Blocks until at least one edge event occurs or the timeout expires.
    Timeout: Time in milliseconds.  `0` returns immediately (for polling).  `None` blocks indefinitely.
    """
    try:
        req = _REQUESTS[port]
    except KeyError:
        return None
    else:
        if req.wait_edge_events(timeout):
            return req.read_edge_events()
        return []
