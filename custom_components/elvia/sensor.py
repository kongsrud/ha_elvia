"""elvia sensors."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ENERGY_KILO_WATT_HOUR
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_registry import (  # async_get as async_get_entity_reg,
    EntityRegistry,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import dt as dt_util

from .const import COST_PERIOD, DOMAIN, MAX_HOURS, METER, METER_READING, TOKEN
from elvia.elvia import CostTimeSpan, Elvia, ElviaApi, Meter
from elvia.elvia_schema import (
    MaxHours,
    MeterValues,
    maxHour,
    maxHourAggregate,
    meteringPointV2,
)

_LOGGER = logging.getLogger(__name__)

datetime_format: str = "%Y-%m-%dT%H:%M:%S%z"


# https://github.com/adafycheng/home-assistant-components/blob/main/dummy-garage/homeassistant/components/dummy_garage/sensor.py


def entity_exists(reg: EntityRegistry, uid) -> bool:
    """Check if entity is already added."""
    fuid = reg.async_get_entity_id("sensor", DOMAIN, uid)
    print("Uid", uid, "fuid", fuid)
    return fuid is not None


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Elvia Sensor."""
    elvia_api: ElviaApi = ElviaApi(hass.data[TOKEN])

    max_hours: bool = hass.data[MAX_HOURS]
    meter_reading: bool = hass.data[METER_READING]
    cost_period: bool = hass.data[COST_PERIOD]

    coordinator = ElviaCoordinator(
        hass, elvia_api, max_hours=max_hours, meter_reading=meter_reading
    )
    await coordinator.async_config_entry_first_refresh()

    #    entity_registry = async_get_entity_reg(hass)

    entities: list[ElviaSensor] = []

    if cost_period:
        entities.append(ElviaEnergyFixedLinkSensor("Grid Cost Period"))

    meter: Meter = hass.data[METER]

    if meter_reading:
        for meter_id in meter.meter_ids:
            entities.append(
                ElviaMeterReadingLevelSensor(
                    coordinator, "Meter Reading", meter_id)
            )

    if max_hours and meter is not None:
        entities.extend(
            await async_create_max_hours(
                hass=hass,
                coordinator=coordinator,
                meter=meter,
            )
        )

    #    entities_to_add = list(
    #        filter(
    #            lambda ent: entity_exists(entity_registry, ent.unique_id) is False,
    #            entities,
    #        )
    #    )
    #
    #    for entity in entities:
    #        if entity not in entities:
    #            _LOGGER.info("Updating entity: ", entity.unique_id)
    #            entity_registry.async_update_entity(entity_id=entity.unique_id)
    #

    # async_add_entities(entities_to_add, True)
    for entity in entities:
        if isinstance(entity, ElviaMeterSensor):
            await entity.async_update()
    async_add_entities(entities, True)


async def async_create_max_hours(
    hass: HomeAssistant,
    coordinator: ElviaCoordinator,
    meter: Meter,
) -> list[ElviaSensor]:
    """Return configured Elvia Max Hour entities."""
    entities: list[ElviaSensor] = []

    _LOGGER.info("Using stored Meter for Elvia Max Hours")
    _LOGGER.info("Creating Elvia Max Hours sensors")

    for meter_id in meter.meter_ids:

        # Elvia calculates peak values in 3 sets
        # If elvia changes this, the integration has to be updated
        for peak in range(3):
            entities.append(
                ElviaMaxHourPeakSensor(coordinator, f"Max Hour {peak}", meter_id, peak)
            )
        entities.append(
            ElviaMaxHourFixedLevelSensor(coordinator, "Max Hours", meter_id)
        )
        entities.append(ElviaFixedGridLevelSensor(coordinator, "Grid Level", meter_id))

    return entities


class ElviaCoordinator(DataUpdateCoordinator):
    """Elvia Data Pull Coordinator.

    Elvia might rete limit if data pull is too often...
    """

    elvia_api: ElviaApi
    config_pull_max_hours: bool = False
    config_pull_meter_reading: bool = False

    data_max_hours: MaxHours
    data_meter_reading: MeterValues

    # https://developers.home-assistant.io/docs/integration_fetching_data/
    def __init__(
        self,
        hass: HomeAssistant,
        elvia_api: ElviaApi,
        max_hours: bool,
        meter_reading: bool,
    ) -> None:
        """Initialize coordinator.

        Fetching setting.
        """
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name="Elvia Meter",
            update_interval=timedelta(minutes=15),
            update_method=self.async_elvia_pull,
        )
        self.elvia_api = elvia_api
        self.config_pull_max_hours = max_hours
        self.config_pull_meter_reading = meter_reading

    async def async_elvia_pull(self) -> None:
        """Fetch relevant data from elvia."""
        if self.config_pull_max_hours:
            result = await self.elvia_api.get_max_hours()
            if isinstance(result.data, MaxHours):
                self.data_max_hours = result.data
        if self.config_pull_meter_reading:
            result = await self.elvia_api.get_meter_values()
            if isinstance(result.data, MeterValues):
                self.data_meter_reading = result.data


class ElviaSensor(SensorEntity):
    """Base sensor class."""

    _attr_has_entity_name: bool = True

    def __init__(self) -> None:
        """Class init."""
        self._attr_extra_state_attributes = {}


class ElviaMeterSensor(CoordinatorEntity, ElviaSensor):
    """Base meter sensor class."""

    _meter_id: str
    _coordinator: ElviaCoordinator

    def __init__(
        self,
        coordinator: ElviaCoordinator,
        name: str,
        meter_id: str,
    ) -> None:
        """Class init."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._meter_id = meter_id
        self._attr_name = f"Elvia Meter {meter_id} {name}"
        self._attr_unique_id = f"elvia_meter_{meter_id}_{name}"

        _LOGGER.info("Setting up %s", self._attr_unique_id)

    async def async_update(self) -> None:
        """Visibility."""
        return await super().async_update()

    def get_meter_id(self) -> str | None:
        """Return meter id."""
        return (
            self._meter_id
            if self._meter_id is not None
            else self.meter_id_from_unique_id()
        )

    def meter_id_from_unique_id(self) -> str | None:
        """Obtain meter id from unique id."""
        if self.unique_id is None:
            return None
        uid = self.unique_id.split("_")[2]
        return uid

    def get_max_hours(self) -> MaxHours | None:
        """Return stored data of max hours."""
        return self._coordinator.data_max_hours

    def get_meter_readings(self) -> MeterValues | None:
        """Return stored data of meter readings."""
        return self._coordinator.data_meter_reading

    def get_attr_end_time(self) -> str | None:
        """Return end_time value from attribute or None."""
        return (
            self._attr_extra_state_attributes["end_time"]
            if (
                self._attr_extra_state_attributes is not None
                and "end_time" in self._attr_extra_state_attributes
            )
            else None
        )

    def can_pull_new_data(self) -> bool:
        """Check wenether the sensor is allowed to pull new data.

        If data_ref is None, pull will be allowed
        """
        now = dt_util.now()
        end_time = self.get_attr_end_time()

        dts: datetime = (
            datetime.strptime(end_time, datetime_format)
            if end_time is not None
            else datetime.now(timezone.utc).replace(
                day=1, month=1, year=1970, hour=0, minute=0, second=1, microsecond=0
            )
        )

        allow_new_pull: datetime = dts + timedelta(hours=1)
        return now >= allow_new_pull

    def get_self_max_hours(self) -> meteringPointV2 | None:
        """Return Max Hour for self meter id or None."""
        all_max_hours = self.get_max_hours()
        if all_max_hours is None:
            _LOGGER.error("Elvia Max Hours is None")
            return None

        _meter_id = self.meter_id_from_unique_id()
        if _meter_id is None:
            _LOGGER.error("Could not find meter id")
            return None

        return Elvia().extract_max_hours(
            meter_id=_meter_id, mtrpoints=all_max_hours.meteringpoints
        )


class ElviaValueSensor(ElviaSensor):
    """Base value sensor class."""

    def __init__(self, name: str) -> None:
        """Class init. Default assignment."""
        super().__init__()

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_name = name = f"Elvia {name}"
        self._attr_unique_id = f"elvia_{name}"

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:cash"


class ElviaFixedGridLevelSensor(ElviaMeterSensor):
    """Sensor for grid level.

    Displays the current monthly fixed grid level.
    The fixed grid level resets every start of the month, but will only increase depending om Max Hours calculated.
    """

    def __init__(
        self,
        coordinator: ElviaCoordinator,
        name: str,
        meter_id: str,
    ) -> None:
        """Class init. Default assignment."""

        super().__init__(coordinator, name=name, meter_id=meter_id)
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = "Level"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update from elvia."""
        max_hours = self.get_self_max_hours()
        max_hours_current: maxHourAggregate | None

        _LOGGER.info("Updating Elvia Grid Level")
        elvia = Elvia()

        _meter_id = self.meter_id_from_unique_id()
        if _meter_id is None:
            return

        if max_hours is None:
            return
        max_hours_current = elvia.extract_max_hours_current(max_hours)
        if len(max_hours_current.maxHours) == 0:
            now = datetime.now()
            self._attr_native_value = elvia.get_grid_level(0)
            self._attr_extra_state_attributes = {
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
                "calculated_time": now.isoformat(),
            }
        else:
            self._attr_native_value = elvia.get_grid_level(
                max_hours_current.averageValue
            )
            self._attr_extra_state_attributes = {
                "start_time": max_hours.maxHoursFromTime,
                "end_time": max_hours.maxHoursToTime,
                "calculated_time": max_hours.maxHoursCalculatedTime,
            }

        return super()._handle_coordinator_update()

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:trending-up"


class ElviaMaxHourFixedLevelSensor(ElviaMeterSensor):
    """Sensor for max hours."""

    def __init__(
        self,
        coordinator: ElviaCoordinator,
        name: str,
        meter_id: str,
    ) -> None:
        """Class init. Default assignment."""
        super().__init__(coordinator, name=name, meter_id=meter_id)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
            "calculated_time": None,
            "grid_level": None,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update from elvia."""

        max_hours = self.get_self_max_hours()
        max_hours_current: maxHourAggregate | None

        _LOGGER.info("Updating Elvia Max Hours")

        if max_hours is None:
            return

        max_hours_current = Elvia().extract_max_hours_current(max_hours)
        
        if len(max_hours_current.maxHours) == 0:
            now = datetime.now()
            self._attr_native_value = 0.00
            self._attr_extra_state_attributes = {
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
                "calculated_time": now.isoformat(),
            }
        else:
            self._attr_native_value = round(
                max_hours_current.averageValue, 2
            )  # Nettleie nivå her
            self._attr_extra_state_attributes = {
                "start_time": max_hours.maxHoursFromTime,
                "end_time": max_hours.maxHoursToTime,
                "calculated_time": max_hours.maxHoursCalculatedTime,
            }

        return super()._handle_coordinator_update()

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:transmission-tower"


class ElviaMeterReadingLevelSensor(ElviaMeterSensor):
    """Sensor for meter reading."""

    def __init__(
        self,
        coordinator: ElviaCoordinator,
        name: str,
        meter_id: str,
    ) -> None:
        """Class init. Default assignment."""

        super().__init__(coordinator, name=name, meter_id=meter_id)

        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update from elvia."""

        _LOGGER.info("Updating Elvia Meter Reading")

        _meter_id = self.meter_id_from_unique_id()
        if _meter_id is None:
            return

        _meter_readings = self.get_meter_readings()
        if _meter_readings is None:
            return

        # Select meter reading matching meter ID
        _meter_values = list(filter(lambda meter: meter.meteringPointId ==
                             _meter_id, _meter_readings.meteringpoints))[0].meterValue
        _LOGGER.debug("Hourly consumption from {} to {}".format(
            _meter_values.fromHour, _meter_values.toHour))

        # Sort hours chronological
        _time_series = sorted(_meter_values.timeSeries,
                              key=lambda series: series.startTime)
        _hourly_consumption = list(
            map(lambda series: series.value,  _time_series))
        _accumulated_consumption_today = sum(_hourly_consumption)
        _LOGGER.debug("Accumulative consumption of {} for {} hours ({})".format(
            _accumulated_consumption_today, len(_hourly_consumption), _hourly_consumption))

        _updated_value = round(_accumulated_consumption_today, 2)
        if (_updated_value != self._attr_native_value):
            if (self._attr_native_value is not None and _updated_value < self._attr_native_value):
                _LOGGER.info(
                    "Resetting meter sensor to 0 kWh before first entry in new period")
                self._attr_native_value = 0
                self.async_write_ha_state()
            self._attr_native_value = _updated_value
            self._attr_extra_state_attributes = {
                "start_time": _time_series[0].startTime if len(_time_series) > 0 else _meter_values.fromHour,
                "end_time": _time_series[-1].endTime if len(_time_series) > 0 else _meter_values.fromHour,
                "hourly_consumption": list(map(lambda value: round(value, 2), _hourly_consumption))
            }

        return super()._handle_coordinator_update()

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:gauge"


class ElviaMaxHourPeakSensor(ElviaMeterSensor):
    """Sensor for max hours."""

    peak_index: int

    def __init__(
        self,
        coordinator: ElviaCoordinator,
        name: str,
        meter_id: str,
        peak_index: int = 0,
    ) -> None:
        """Class init. Default assignment."""

        self.peak_index = peak_index
        super().__init__(coordinator, name=name, meter_id=meter_id)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR

        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update from elvia."""

        max_hours = self.get_self_max_hours()
        peak_hour: maxHour

        _LOGGER.info("Updating Elvia Max Hours Peak")

        _meter_id = self.meter_id_from_unique_id()
        if _meter_id is None:
            return

        if max_hours is None:
            return
        max_hours_current = Elvia().extract_max_hours_current(max_hours)
        if (
            max_hours_current is None
            or len(max_hours_current.maxHours) < self.peak_index
        ):
            now = datetime.now()
            self._attr_native_value = 0.00
            self._attr_extra_state_attributes = {
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(hours=1)).isoformat(),
            }
            return
        else: 
            peak_hour = max_hours_current.maxHours[self.peak_index]

            self._attr_native_value = round(peak_hour.value, 2)
            self._attr_extra_state_attributes = {
                "start_time": max_hours.maxHoursFromTime,
                "end_time": max_hours.maxHoursToTime,
            }

        return super()._handle_coordinator_update()

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:meter-electric"


class ElviaEnergyFixedLinkSensor(ElviaValueSensor):
    """Sensor for current fixed link cost."""

    def __init__(self, name: str) -> None:
        """Class init. Default assignment."""
        super().__init__(name)

        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_native_unit_of_measurement = "NOK"

        self._attr_extra_state_attributes = {
            "start_time": None,
            "end_time": None,
        }

    async def async_update(self) -> None:
        """Fetch new values for the sensor."""
        elvia = Elvia()
        period = elvia.get_cost_period_now(now=dt_util.now())
        if period is None:
            return

        self._attr_native_value = period.cost

        periods = elvia.get_cost_periods()
        day_period: CostTimeSpan = periods["day"]
        night_period: CostTimeSpan = periods["night"]
        weekend_period: CostTimeSpan = periods["weekend"]

        self._attr_extra_state_attributes = {
            "friendly_name": "Grid cost period",
            "currency": "NOK",
            "now_period": f"{period.start_time} - {period.end_time}",
            "day_period": f"{day_period.start_time} - {day_period.end_time}",
            "day_cost": day_period.cost,
            "night_period": f"{night_period.start_time} - {night_period.end_time}",
            "night_cost": night_period.cost,
            "weekend_period": f"{weekend_period.start_time} - {weekend_period.end_time}",
            "weekend_cost": weekend_period.cost,
        }

    @property
    def icon(self) -> str:
        """Icon of the entity."""
        return "mdi:cash"
