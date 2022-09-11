"""Schema for Pykson."""
# https://github.com/sinarezaei/pykson

from pykson import (
    BooleanField,
    FloatField,
    IntegerField,
    JsonObject,
    ObjectField,
    ObjectListField,
    StringField,
)


# https://elvia.portal.azure-api.net/docs/services/metervalueapi/operations/get-api-v2-maxhours?
# pylint: disable=invalid-name
class maxHour(JsonObject):
    """Schema object."""

    startTime = StringField(serialized_name="startTime")
    endTime = StringField(serialized_name="endTime")
    value = FloatField(serialized_name="value")
    uom = StringField(serialized_name="uom")
    noOfMonthsBack = IntegerField(serialized_name="noOfMonthsBack")
    production = BooleanField(serialized_name="production")
    verified = BooleanField(serialized_name="verified")

    def __str__(self) -> str:
        """Override default str in order to get data as a string."""
        return "startTime: {startTime}, endTime: {endTime}, value: {value}".format(
            startTime=self.startTime, endTime=self.endTime, value=str(self.value)
        )


# pylint: disable=invalid-name
class maxHourAggregate(JsonObject):
    """Schema object."""

    averageValue = FloatField(serialized_name="averageValue")
    maxHours: list[maxHour] = ObjectListField(maxHour, serialized_name="maxHours")
    uom = StringField(serialized_name="uom")
    noOfMonthsBack = IntegerField(serialized_name="noOfMonthsBack")

    def __str__(self) -> str:
        """Override default str in order to get data as a string."""
        return f"Average {self.averageValue}Kwh, MaxHours {self.maxHours}"


# pylint: disable=invalid-name
class contractV2(JsonObject):
    """Schema object."""

    startDate = StringField(serialized_name="startDate")
    endDate = StringField(serialized_name="endDate")


# pylint: disable=invalid-name
class meteringPointV2(JsonObject):
    """Schema object."""

    meteringPointId = StringField(serialized_name="meteringPointId")
    maxHoursCalculatedTime = StringField(serialized_name="maxHoursCalculatedTime")
    maxHoursFromTime = StringField(serialized_name="maxHoursFromTime")
    maxHoursToTime = StringField(serialized_name="maxHoursToTime")
    customerContract: contractV2 = ObjectField(
        contractV2, serialized_name="customerContract"
    )
    maxHoursAggregate: list[maxHourAggregate] = ObjectListField(
        maxHourAggregate, serialized_name="maxHoursAggregate"
    )


class MaxHours(JsonObject):
    """Schema object."""

    meteringpoints: list[meteringPointV2] = ObjectListField(
        meteringPointV2, serialized_name="meteringpoints"
    )


# https://elvia.portal.azure-api.net/docs/services/metervalueapi/operations/get-api-v1-metervalues?


# pylint: disable=invalid-name
class timeSerie(JsonObject):
    """Schema object."""

    start_time = StringField(serialized_name="startTime")
    end_time = StringField(serialized_name="endTime")
    value = FloatField(serialized_name="value")
    uom = StringField(serialized_name="uom")
    production = BooleanField(serialized_name="production")
    verified = BooleanField(serialized_name="verified")


# pylint: disable=invalid-name
class meterValue(JsonObject):
    """Schema object."""

    from_hour = StringField(serialized_name="fromHour")
    to_hour = StringField(serialized_name="toHour")
    resolution_minutes = IntegerField(serialized_name="resolutionMinutes")
    time_series: list[timeSerie] = ObjectListField(
        timeSerie, serialized_name="timeSeries"
    )


# pylint: disable=invalid-name
class contractV1(JsonObject):
    """Schema object."""

    start_time = StringField(serialized_name="startTime")
    end_time = StringField(serialized_name="endTime")


# pylint: disable=invalid-name
class meteringPointV1(JsonObject):
    """Schema object."""

    metering_point_id = StringField(serialized_name="meteringPointId")
    customer_contract: contractV1 = ObjectField(
        contractV1, serialized_name="customerContract"
    )
    meter_value: meterValue = ObjectField(meterValue, serialized_name="metervalue")


class MeterValues(JsonObject):
    """Schema object."""

    meteringpoints: list[meteringPointV1] = ObjectListField(
        meteringPointV1, serialized_name="meteringpoints"
    )
