"""Interface with libgpiod."""


import datetime
import logging
import gpiod


from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "gpio"
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.SWITCH,
]

def _guess_default_device():
    default_device = "/dev/gpiochip0"
    try:
        with open("/sys/firmware/devicetree/base/model") as model_file:
            model_string = model_file.read()
    except IOError:
        return default_device
    else:
        if "Raspberry Pi 5 Model B" in model_string:
            default_device = "/dev/gpiochip4"
        # Add more platform-specific default device logic here
        # elif ...:
        #     default_device = ...        
    _LOGGER.debug("Default GPIO device: %s", default_device)
    return default_device

DEFAULT_DEVICE = _guess_default_device()


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
    _LOGGER.debug("Requesting output %s:%s", device, port)
    return _configure_line(
        device, 
        port, 
        direction=gpiod.line.Direction.OUTPUT)


def setup_input(device, port, pull_mode):
    """Set up a GPIO as input."""
    _LOGGER.debug("Requesting input %s:%s", device, port)
    return _configure_line(
        device,
        port, 
        direction=gpiod.line.Direction.INPUT,
        bias=(gpiod.line.Bias.PULL_DOWN if pull_mode == "DOWN" else gpiod.line.Bias.PULL_UP))


def enable_edge_detect(req, detect_edges, debounce_ms):
    """Add detection for RISING and FALLING events."""
    _LOGGER.debug("Detecting %s edges on %s:%s", detect_edges, req.chip_name, req.lines)
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
    _LOGGER.debug("Writing %s on %s:%s", value, req.chip_name, port)
    req.set_values({port: gpiod.line.Value.ACTIVE if value else gpiod.line.Value.INACTIVE})


def read_input(req):
    """Read a value from a GPIO."""
    assert (req.num_lines == 1)
    port = req.lines[0]
    _LOGGER.debug("Reading %s:%s", req.chip_name, port)
    return (req.get_value(port) == gpiod.line.Value.ACTIVE)


def read_edge_events(req, timeout):
    """
    Blocks until at least one edge event occurs or the timeout expires.
    Timeout: Time in milliseconds.  `0` returns immediately (for polling).  `None` blocks indefinitely.
    """
    if req.wait_edge_events(timeout):
        events = req.read_edge_events()
        for event in events:
            _LOGGER.debug("Edge event on %s:%s: %s", req.chip_name, req.lines, event)
        return events
    return []
