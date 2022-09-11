"""elvia communication."""
from __future__ import annotations

import datetime
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

import aiohttp
from pykson import Pykson

from .elvia_schema import MaxHours, MeterValues, maxHourAggregate, meteringPointV2


class ElviaWebResponse:
    """Data class to wrap api response."""

    json: str
    status_code: int = 0  # Http status code

    def __init__(self, status_code: int, json: str) -> None:
        """Class init. Returns nothing."""
        self.json = json
        self.status_code = status_code


class CostTimeSpan:
    """Elvia cost time span."""

    start_time: float = 0.0
    end_time: float = 0.0
    cost: float = 0.0

    def __init__(self, start_time: float, end_time: float, cost: float) -> None:
        """Class init."""
        self.start_time = start_time
        self.end_time = end_time
        self.cost = cost


class Meter:
    """Data class for storing info."""

    success: bool = False
    status_code: int = 404
    meter_ids: list[str]

    def __init__(self, status_code: int, meter_ids: list[str]) -> None:
        """Class init."""
        self.success = status_code == 200
        self.status_code = status_code
        self.meter_ids = meter_ids


class ElviaData:
    """Data class for wrapping deserialized result."""

    status_code: int = 404
    data: MaxHours | MeterValues | Meter | None = None

    def __init__(self, status_code: int, data: Any) -> None:
        """Class init. Returns nothing."""
        self.status_code = status_code
        self.data = data


class ElviaApi:
    """Communication class for elvia."""

    domain = "elvia.azure-api.net"
    jwt: str

    meter: Meter
    max_hours: MaxHours
    meter_values: MeterValues

    def __init__(self, jwt: str) -> None:
        """Class init. Returns nothing."""
        self.jwt = jwt

    # pylint: disable=invalid-name,broad-except,no-member
    async def request_elvia_for_response(
        self, path, timeout_sec: int = 30
    ) -> ElviaWebResponse:
        """Return WebResponse data from elvia."""

        headers = {"Authorization": "Bearer %s" % self.jwt}
        request_timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with aiohttp.ClientSession(
            headers=headers, timeout=request_timeout
        ) as session:
            url = "https://" + self.domain + path

            async with session.get(url) as response:
                payload = await response.read()
                json_string = str(payload, "utf-8")
                elvia_response: ElviaWebResponse = ElviaWebResponse(
                    response.status, json_string
                )
                return elvia_response

    async def get_meters(self, timeout_sec: int = 30) -> Meter:
        """Return Meter with owned meter ids."""
        now = datetime.datetime.now(datetime.timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        params = urllib.parse.urlencode(
            {
                "startTime": now.isoformat(),
                "endTime": (now + datetime.timedelta(hours=1)).isoformat(),
            }
        )

        response: ElviaWebResponse = await self.request_elvia_for_response(
            "/customer/metervalues/api/v1/metervalues?%s" % params
        )

        if response.status_code != 200:
            raise Exception("Response is not OK", response.status_code, response.json)

        meter_values: MeterValues = Pykson().from_json(response.json, MeterValues)
        meters = meter_values.meteringpoints
        meter_ids = [item.metering_point_id for item in meters]

        return Meter(response.status_code, meter_ids)

    # pylint: disable=dangerous-default-value
    async def get_meter_values(
        self,
        metering_ids: list[str] = [],
        include_production: bool = False,
        timeout_sec: int = 30,
    ) -> ElviaData:
        """Return ElviaData with recorded meter values."""

        params = urllib.parse.urlencode(
            {
                # Request parameters
                #    "startTime": "{string}",
                #    "endTime": "{string}",
                #    "meteringPointIds": "{array}",
                "includeProduction": include_production,
            }
        )

        response: ElviaWebResponse = await self.request_elvia_for_response(
            "/customer/metervalues/api/v1/metervalues?%s" % params
        )
        if response.status_code != 200:
            raise Exception("Response is not OK", response.status_code, response.json)

        meter_values: MeterValues = Pykson().from_json(response.json, MeterValues)
        return ElviaData(response.status_code, meter_values)

    # pylint: disable=dangerous-default-value
    async def get_max_hours(
        self,
        metering_ids: list[str] = [],
        include_production: bool = False,
        timeout_sec: int = 30,
    ) -> ElviaData:
        """Return ElviaData with recorded max hours.

        This defines the monthly grid level.
        """

        params = urllib.parse.urlencode(
            {
                # Request parameters
                #           'calculateTime': '{string}',
                #           'meteringPointIds': '{array}',
                "includeProduction": include_production,
            }
        )

        response: ElviaWebResponse = await self.request_elvia_for_response(
            "/customer/metervalues/api/v2/maxhours?%s" % params
        )
        if response.status_code != 200:
            raise Exception("Response is not HTTP 200", response.json)

        max_hours: MaxHours = Pykson().from_json(response.json, MaxHours)
        return ElviaData(response.status_code, max_hours)

    async def update_meters(self) -> None:
        """Return None. Executes request for meter ids."""
        meter_data = await self.get_meters()
        self.meter = meter_data

    async def update_max_hours(self) -> None:
        """Request update of max hours and store it in object/class."""
        elvia_data = await self.get_max_hours()
        if elvia_data.status_code != 200:
            raise Exception("Elvia response is not OK!", elvia_data.data)
        max_hours_data = elvia_data.data
        if isinstance(max_hours_data, MaxHours) and max_hours_data is not None:
            self.max_hours = max_hours_data

    async def update_meter_values(self) -> None:
        """Request update of meter values and store it in object/class."""
        elvia_data = await self.get_max_hours()
        if elvia_data.status_code != 200:
            raise Exception("Elvia response is not OK!", elvia_data.data)
        meter_values = elvia_data.data
        if isinstance(meter_values, MeterValues) and meter_values is not None:
            self.meter_values = meter_values


class Elvia:
    """Communication class for elvia."""

    def __init__(self) -> None:
        """Class init. Returns nothing."""

    def extract_max_hours(
        self, meter_id: str, mtrpoints: list[meteringPointV2]
    ) -> meteringPointV2 | None:
        """Return meteringPointV2 based on meter id."""
        return next(
            (
                meter_max
                for meter_max in mtrpoints
                if meter_max.meteringPointId == meter_id
            ),
            None,
        )

    def extract_max_hours_current(
        self, point: meteringPointV2
    ) -> maxHourAggregate | None:
        """Return current maxHourAggregate.

        Return will be of None if data is None or noOfMonthsBack is not 0.
        """
        data = (
            None
            if point is None or len(point.maxHoursAggregate) == 0
            else point.maxHoursAggregate[0]
        )
        if data is None:
            return data
        if data.noOfMonthsBack != 0:
            raise DataIsNotOfCurrentMonth(
                f"Data is not of current, but of {data.noOfMonthsBack} months back"
            )
        return data

    def get_grid_level(self, kwh: float) -> int:
        """Calculate the grid level based on kwh."""
        if kwh <= 2:
            return 1
        if 5 >= kwh > 2:
            return 2
        if 10 >= kwh > 5:
            return 3
        if 15 >= kwh > 10:
            return 4
        if 20 >= kwh > 15:
            return 5
        if 25 >= kwh > 20:
            return 6
        if 50 >= kwh > 25:
            return 7
        if 75 >= kwh > 50:
            return 8
        if 100 >= kwh > 75:
            return 9
        return 10

    def get_cost_periods(self) -> dict[str, CostTimeSpan]:
        """Return instances of cost.

        Consists of keys: day, night, weekend
        weekend = saturday to sunday + holidays
        """
        return {
            "day": CostTimeSpan(6, 22, cost=43.10),
            "night": CostTimeSpan(22, 6, cost=36.85),
            "weekend": CostTimeSpan(0, 0, cost=36.85),
        }

    def get_cost_period_now(self, now: datetime.datetime) -> CostTimeSpan | None:
        """Return fixed grid cost for the current time."""
        periods = self.get_cost_periods()
        cost_time_span: CostTimeSpan
        if now.isoweekday() in [6, 7]:
            cost_time_span = periods["weekend"]
        elif now.hour >= periods["day"].start_time and (
            now.hour < periods["day"].end_time
            or (now.hour == periods["day"].end_time and now.minute == 0)
        ):
            cost_time_span = periods["day"]
        else:
            cost_time_span = periods["night"]

        return cost_time_span


class DataIsNotOfCurrentMonth(Exception):
    """Incorrect data exception occurred."""
