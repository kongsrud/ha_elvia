"""The elvia integration."""
from __future__ import annotations

import asyncio

# from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import COST_PERIOD, MAX_HOURS, METER, METER_READING, TOKEN
from elvia.elvia import ElviaApi

PLATFORMS: list[Platform] = [Platform.SENSOR]


# pylint: disable=fixme
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up elvia from a config entry."""

    hass.data[TOKEN] = entry.data[TOKEN]
    hass.data[MAX_HOURS] = entry.data[MAX_HOURS]
    hass.data[METER_READING] = entry.data[METER_READING]
    hass.data[COST_PERIOD] = entry.data[COST_PERIOD]

    try:
        result = await ElviaApi(entry.data[TOKEN]).get_meters()
        hass.data[METER] = result
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady from err

    # IF NEEDED: entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


# https://dev.to/adafycheng/write-custom-component-for-home-assistant-4fce
