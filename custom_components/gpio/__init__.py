"""Interface with libgpiod."""


import datetime
import gpiod


from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "gpio"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SWITCH,
]

DEFAULT_DEVICE = "/dev/gpiochip4"


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the GPIO component."""
    
    def cleanup_gpio(event):
        """Stuff to do before stopping."""

    def prepare_gpio(event):
        """Stuff to do when Home Assistant starts."""

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)
    return True


def _configure_line(device, port, **kwargs):
    return gpiod.request_lines(
        device, 
        consumer=DOMAIN, 
        config={port: gpiod.LineSettings(**kwargs)})


def setup_output(device, port):
    """Set up a GPIO as output."""
    return _configure_line(
        device, 
        port, 
        direction=gpiod.line.Direction.OUTPUT)


def setup_input(device, port, pull_mode):
    """Set up a GPIO as input."""
    return _configure_line(
        device,
        port, 
        direction=gpiod.line.Direction.INPUT,
        bias=(gpiod.line.Bias.PULL_DOWN if pull_mode == "DOWN" else gpiod.line.Bias.PULL_UP))


def enable_edge_detect(req, detect_edges, debounce_ms):
    """Add detection for RISING and FALLING events."""
    edge_detection = {
        "BOTH": gpiod.line.Edge.BOTH,
        "RISING": gpiod.line.Edge.RISING,
        "FALLING": gpiod.line.Edge.FALLING
    }[detect_edges]
    req.reconfigure_lines(
        {port: gpiod.LineSettings(edge_detection=edge_detection,
                                  debounce_period=datetime.timedelta(milliseconds=debounce_ms))
         for port in req.lines})


def write_output(req, value):
    """Write a value to a GPIO."""
    assert (req.num_lines == 1)
    port = req.lines[0]
    req.set_values({port: gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE})


def read_input(req):
    """Read a value from a GPIO."""
    assert (req.num_lines == 1)
    port = req.lines[0]
    return (req.get_value(port) == gpiod.line.Value.ACTIVE)


def read_edge_events(req, timeout):
    """
    Blocks until at least one edge event occurs or the timeout expires.
    Timeout: Time in milliseconds.  `0` returns immediately (for polling).  `None` blocks indefinitely.
    """
    if req.wait_edge_events(timeout):
        return req.read_edge_events()
    return []
