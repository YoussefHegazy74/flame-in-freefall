"""Parser for the SAME-R HKP housekeeping/telemetry CSV series (PSI-101).

All 44 selected HKP files share one exact 98-column header. Each file is a
separate run. The parser keeps run identity in ``smoke_run`` and emits a tidy
``smoke_point`` table with explicit sentinel, constant, uncalibrated, and
unit-less flags. Device state and actuator columns are preserved as channels;
they are not reinterpreted as physical measurements.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from ..config import PARSER_VERSION
from ..provenance import SourceFile, observation_id, raw_row_json
from .base import ParseIssue, parse_number, require_exact_header, row_is_empty


SMOKE_HEADER: list[str] = [
    "TimeString",
    "Time",
    "RunMode",
    "TestNumber",
    "ElapsedTestTime(Secs)",
    "SampleNumber",
    "CarouselNumber",
    "DriveKBRemaining",
    "CycleCounter",
    "WatchdogReset",
    "EnetSelect",
    "EnetOverride",
    "OKStatus",
    "EventSet",
    "EventCode",
    "TestRunning",
    "12VDCHeaterEnable",
    "HeatingInProgress",
    "SampleHeaterOverride",
    "GasPlumeTemperature(DegC)",
    "SampleResistance(Ohms)",
    "ISSDetectorObscurationMeasurement(Volts)",
    "ISSDetectorScatterMeasurement(Volts)",
    "STSDetectorMeasurement(Volts)",
    "IonDetectorAMeasurement(Volts)",
    "IonDetectorBMeasurement(Volts)",
    "PTrakMeasurement(PtPerCC)",
    "DustTrakAMeasurement(MgPerM3)",
    "DustTrakBMeasurement(MgPerM3)",
    "DustTrakAAnalogMeasurement(Volts)",
    "DustTrakBAnalogMeasurement(Volts)",
    "LFEFlowRate[AT08](SCCM)",
    "VSOSetpoint[PN23](Volts)",
    "ZeroLFE",
    "MFCSetpoint(LPM)",
    "MFCMassFlowRate(LPM)",
    "MFCTemperature(DegC)",
    "MFCPressure(PSIA)",
    "MFCAnalogSetpoint[BN19](LPM)",
    "MFCAnalogFlowRate(LPM)",
    "GN2MainPressure[PN02](PSIA)",
    "GN2RegulatedPressure[PN12](PSIG)",
    "VacuumPressure[VR04](PSIA)",
    "DriveSidePressure[BN02](PSIA)",
    "SampleSidePressure[AT20](PSIA)",
    "ThermalPrecipitatorPreAgeChannel",
    "ThermalPrecipitatorPostAgeChannel",
    "PTrakState",
    "PTrakKeySelect",
    "PTrakPowerMeasurement(Volts)",
    "DustTrakAState",
    "DustTrakAKeySelect",
    "DustTrakBState",
    "DustTrakBKeySelect",
    "ProximitySensor1(Volts)",
    "ProximitySensor2(Volts)",
    "ProximitySensor4(Volts)",
    "CarouselProximitySensor(Volts)",
    "MixingFanPower",
    "PTrakPower",
    "DustTrakAPower",
    "DustTrakBPower",
    "STSDetectorPower",
    "CarouselPower",
    "PositionerEnable",
    "PositionerDirectionIn",
    "PositionerClock",
    "GN2MainSolenoid[PN03]",
    "GateEnableSolenoid[PN07]",
    "InletGateSolenoid[BN08]",
    "OutletGateSolenoid[BN09]",
    "PistonControlSolenoid[BN17]",
    "DynamicDilutorSolenoid[PN15]",
    "PTrakSolenoid[VR06]",
    "CommDiagASolenoid[VR11]",
    "CommDiagBSolenoid[VR12]",
    "CommDiagADilutionSolenoid[PN24]",
    "CommDiagBDilutionSolenoid[PN27]",
    "PurgeSolenoid[VM09]",
    "PistonGN2Solenoid[BN18]",
    "PistonVentSolenoid[BN20]",
    "PistonVacuumSolenoid[BN16]",
    "ThermalPrecipitatorSolenoid[VM06]",
    "ThermalPrecipitatorPreAgeHeater",
    "ThermalPrecipitatorPostAgeHeater",
    "ThermalPrecipitatorPreAgeValve",
    "ThermalPrecipitatorPostAgeValve",
    "ThermalPrecipitatorPreAgeCableSense",
    "ThermalPrecipitatorPostAgeCableSense",
    "STSDetectorSelfTest",
    "STSDetectorAlarmReset",
    "STSDetectorAlarm",
    "ISSDetectorSelfTest",
    "VideoPower",
    "VideoRecording",
    "VideoPaused",
    "CameraPower",
    "IlluminationLEDPower",
]

if len(SMOKE_HEADER) != 98:
    raise RuntimeError("SAME-R header must contain 98 columns")

# Raw name -> (canonical name, unit, uncalibrated voltage).
_CHANNEL_TABLE: dict[str, tuple[str, str, bool]] = {
    "TimeString": ("source_time_string", "not stated", False),
    "Time": ("unix_time_s", "Unix seconds", False),
    "RunMode": ("run_mode_code", "not stated", False),
    "TestNumber": ("test_number", "not stated", False),
    "ElapsedTestTime(Secs)": ("elapsed_test_time_s", "s", False),
    "SampleNumber": ("sample_number", "not stated", False),
    "CarouselNumber": ("carousel_number", "not stated", False),
    "DriveKBRemaining": ("drive_kb_remaining", "KB", False),
    "CycleCounter": ("cycle_counter", "not stated", False),
    "WatchdogReset": ("watchdog_reset", "not stated", False),
    "EnetSelect": ("enet_select", "not stated", False),
    "EnetOverride": ("enet_override", "not stated", False),
    "OKStatus": ("ok_status", "not stated", False),
    "EventSet": ("event_set", "not stated", False),
    "EventCode": ("event_code", "not stated", False),
    "TestRunning": ("test_running", "not stated", False),
    "12VDCHeaterEnable": ("heater_12vdc_enable", "not stated", False),
    "HeatingInProgress": ("heating_in_progress", "not stated", False),
    "SampleHeaterOverride": ("sample_heater_override", "not stated", False),
    "GasPlumeTemperature(DegC)": ("gas_plume_temp_c", "°C", False),
    "SampleResistance(Ohms)": ("sample_resistance_ohm", "Ω", False),
    "ISSDetectorObscurationMeasurement(Volts)": ("iss_detector_obscuration_v", "V", True),
    "ISSDetectorScatterMeasurement(Volts)": ("iss_detector_scatter_v", "V", True),
    "STSDetectorMeasurement(Volts)": ("sts_detector_v", "V", True),
    "IonDetectorAMeasurement(Volts)": ("ion_detector_a_v", "V", True),
    "IonDetectorBMeasurement(Volts)": ("ion_detector_b_v", "V", True),
    "PTrakMeasurement(PtPerCC)": ("ptrak_concentration_pt_cc", "pt/cc", False),
    "DustTrakAMeasurement(MgPerM3)": ("dusttrak_a_mg_m3", "mg/m³", False),
    "DustTrakBMeasurement(MgPerM3)": ("dusttrak_b_mg_m3", "mg/m³", False),
    "DustTrakAAnalogMeasurement(Volts)": ("dusttrak_a_analog_v", "V", True),
    "DustTrakBAnalogMeasurement(Volts)": ("dusttrak_b_analog_v", "V", True),
    "LFEFlowRate[AT08](SCCM)": ("lfe_flow_rate_sccm", "SCCM", False),
    "VSOSetpoint[PN23](Volts)": ("vso_setpoint_v", "V", True),
    "ZeroLFE": ("zero_lfe", "not stated", False),
    "MFCSetpoint(LPM)": ("mfc_setpoint_lpm", "LPM", False),
    "MFCMassFlowRate(LPM)": ("mfc_mass_flow_lpm", "LPM", False),
    "MFCTemperature(DegC)": ("mfc_temperature_c", "°C", False),
    "MFCPressure(PSIA)": ("mfc_pressure_psia", "PSIA", False),
    "MFCAnalogSetpoint[BN19](LPM)": ("mfc_analog_setpoint_lpm", "LPM", False),
    "MFCAnalogFlowRate(LPM)": ("mfc_analog_flow_lpm", "LPM", False),
    "GN2MainPressure[PN02](PSIA)": ("gn2_main_pressure_psia", "PSIA", False),
    "GN2RegulatedPressure[PN12](PSIG)": ("gn2_regulated_pressure_psig", "PSIG", False),
    "VacuumPressure[VR04](PSIA)": ("vacuum_pressure_psia", "PSIA", False),
    "DriveSidePressure[BN02](PSIA)": ("drive_side_pressure_psia", "PSIA", False),
    "SampleSidePressure[AT20](PSIA)": ("sample_side_pressure_psia", "PSIA", False),
    "ThermalPrecipitatorPreAgeChannel": ("thermal_precipitator_pre_age_channel", "not stated", False),
    "ThermalPrecipitatorPostAgeChannel": ("thermal_precipitator_post_age_channel", "not stated", False),
    "PTrakState": ("ptrak_state", "not stated", False),
    "PTrakKeySelect": ("ptrak_key_select", "not stated", False),
    "PTrakPowerMeasurement(Volts)": ("ptrak_power_v", "V", True),
    "DustTrakAState": ("dusttrak_a_state", "not stated", False),
    "DustTrakAKeySelect": ("dusttrak_a_key_select", "not stated", False),
    "DustTrakBState": ("dusttrak_b_state", "not stated", False),
    "DustTrakBKeySelect": ("dusttrak_b_key_select", "not stated", False),
    "ProximitySensor1(Volts)": ("proximity_sensor_1_v", "V", True),
    "ProximitySensor2(Volts)": ("proximity_sensor_2_v", "V", True),
    "ProximitySensor4(Volts)": ("proximity_sensor_4_v", "V", True),
    "CarouselProximitySensor(Volts)": ("carousel_proximity_sensor_v", "V", True),
    "MixingFanPower": ("mixing_fan_power", "not stated", False),
    "PTrakPower": ("ptrak_power_state", "not stated", False),
    "DustTrakAPower": ("dusttrak_a_power_state", "not stated", False),
    "DustTrakBPower": ("dusttrak_b_power_state", "not stated", False),
    "STSDetectorPower": ("sts_detector_power_state", "not stated", False),
    "CarouselPower": ("carousel_power_state", "not stated", False),
    "PositionerEnable": ("positioner_enable", "not stated", False),
    "PositionerDirectionIn": ("positioner_direction_in", "not stated", False),
    "PositionerClock": ("positioner_clock", "not stated", False),
    "GN2MainSolenoid[PN03]": ("gn2_main_solenoid", "not stated", False),
    "GateEnableSolenoid[PN07]": ("gate_enable_solenoid", "not stated", False),
    "InletGateSolenoid[BN08]": ("inlet_gate_solenoid", "not stated", False),
    "OutletGateSolenoid[BN09]": ("outlet_gate_solenoid", "not stated", False),
    "PistonControlSolenoid[BN17]": ("piston_control_solenoid", "not stated", False),
    "DynamicDilutorSolenoid[PN15]": ("dynamic_dilutor_solenoid", "not stated", False),
    "PTrakSolenoid[VR06]": ("ptrak_solenoid", "not stated", False),
    "CommDiagASolenoid[VR11]": ("comm_diag_a_solenoid", "not stated", False),
    "CommDiagBSolenoid[VR12]": ("comm_diag_b_solenoid", "not stated", False),
    "CommDiagADilutionSolenoid[PN24]": ("comm_diag_a_dilution_solenoid", "not stated", False),
    "CommDiagBDilutionSolenoid[PN27]": ("comm_diag_b_dilution_solenoid", "not stated", False),
    "PurgeSolenoid[VM09]": ("purge_solenoid", "not stated", False),
    "PistonGN2Solenoid[BN18]": ("piston_gn2_solenoid", "not stated", False),
    "PistonVentSolenoid[BN20]": ("piston_vent_solenoid", "not stated", False),
    "PistonVacuumSolenoid[BN16]": ("piston_vacuum_solenoid", "not stated", False),
    "ThermalPrecipitatorSolenoid[VM06]": ("thermal_precipitator_solenoid", "not stated", False),
    "ThermalPrecipitatorPreAgeHeater": ("thermal_precipitator_pre_age_heater", "not stated", False),
    "ThermalPrecipitatorPostAgeHeater": ("thermal_precipitator_post_age_heater", "not stated", False),
    "ThermalPrecipitatorPreAgeValve": ("thermal_precipitator_pre_age_valve", "not stated", False),
    "ThermalPrecipitatorPostAgeValve": ("thermal_precipitator_post_age_valve", "not stated", False),
    "ThermalPrecipitatorPreAgeCableSense": ("thermal_precipitator_pre_age_cable_sense", "not stated", False),
    "ThermalPrecipitatorPostAgeCableSense": ("thermal_precipitator_post_age_cable_sense", "not stated", False),
    "STSDetectorSelfTest": ("sts_detector_self_test", "not stated", False),
    "STSDetectorAlarmReset": ("sts_detector_alarm_reset", "not stated", False),
    "STSDetectorAlarm": ("sts_detector_alarm", "not stated", False),
    "ISSDetectorSelfTest": ("iss_detector_self_test", "not stated", False),
    "VideoPower": ("video_power", "not stated", False),
    "VideoRecording": ("video_recording", "not stated", False),
    "VideoPaused": ("video_paused", "not stated", False),
    "CameraPower": ("camera_power", "not stated", False),
    "IlluminationLEDPower": ("illumination_led_power", "not stated", False),
}

SMOKE_CHANNELS = {
    raw: {"canonical": canonical, "unit": unit, "uncalibrated": uncalibrated}
    for raw, (canonical, unit, uncalibrated) in _CHANNEL_TABLE.items()
}
if set(SMOKE_CHANNELS) != set(SMOKE_HEADER):
    raise RuntimeError("SAME-R channel map does not match the exact header")

EXCLUDED_CHANNELS = frozenset(
    {
        "TimeString",
        "Time",
        "ElapsedTestTime(Secs)",
        "TestNumber",
        "SampleNumber",
        "CarouselNumber",
        "RunMode",
    }
)


@dataclass
class SmokeChannelStats:
    raw_name: str
    canonical: str
    unit: str
    uncalibrated: bool
    count: int = 0
    missing: int = 0
    sentinel: int = 0
    nonnumeric: int = 0
    first_value: float | None = None
    all_equal: bool = True
    min_value: float | None = None
    max_value: float | None = None

    def observe(self, value: Any) -> None:
        parsed = parse_number(value)
        raw = parsed.raw
        if raw is None or not str(raw).strip():
            self.missing += 1
            return
        if str(raw).strip() == "-999":
            self.sentinel += 1
            return
        if parsed.value is None:
            self.nonnumeric += 1
            return
        self.count += 1
        if self.first_value is None:
            self.first_value = parsed.value
        elif self.all_equal and parsed.value != self.first_value:
            self.all_equal = False
        if self.min_value is None or parsed.value < self.min_value:
            self.min_value = parsed.value
        if self.max_value is None or parsed.value > self.max_value:
            self.max_value = parsed.value

    @property
    def constant(self) -> bool:
        return self.count >= 2 and self.all_equal

    def as_dict(self) -> dict[str, Any]:
        return {
            "raw_name": self.raw_name,
            "canonical_name": self.canonical,
            "unit": self.unit,
            "uncalibrated": self.uncalibrated,
            "count": self.count,
            "missing": self.missing,
            "sentinel": self.sentinel,
            "nonnumeric": self.nonnumeric,
            "min": self.min_value,
            "max": self.max_value,
            "constant": self.constant,
        }


@dataclass
class SmokeScan:
    source: SourceFile
    header: list[str]
    stats: list[SmokeChannelStats]
    physical_rows: int = 0
    empty_rows: int = 0
    malformed_rows: int = 0
    invalid_time_rows: int = 0
    sentinel_time_rows: int = 0
    valid_rows: int = 0
    issues: list[ParseIssue] = field(default_factory=list)
    time_min_unix_s: int | None = None
    time_max_unix_s: int | None = None
    elapsed_min_s: float | None = None
    elapsed_max_s: float | None = None
    test_numbers: set[int] = field(default_factory=set)
    sample_numbers: set[int] = field(default_factory=set)
    carousel_numbers: set[int] = field(default_factory=set)
    run_mode_codes: set[int] = field(default_factory=set)

    @property
    def run_id(self) -> str:
        return f"PSI-101::{Path(self.source.file_name).stem}"

    @property
    def constant_channels(self) -> set[str]:
        return {stats.raw_name for stats in self.stats if stats.constant}

    @property
    def sentinel_channels(self) -> set[str]:
        return {stats.raw_name for stats in self.stats if stats.sentinel}

    def channel_profiles(self) -> list[dict[str, Any]]:
        return [stats.as_dict() for stats in self.stats]

    def as_run_record(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "accession": "PSI-101",
            "source_file": self.source.file_name,
            "test_number": next(iter(self.test_numbers)) if len(self.test_numbers) == 1 else None,
            "sample_number": next(iter(self.sample_numbers)) if len(self.sample_numbers) == 1 else None,
            "carousel_number": next(iter(self.carousel_numbers)) if len(self.carousel_numbers) == 1 else None,
            "test_numbers_json": json.dumps(sorted(self.test_numbers)),
            "sample_numbers_json": json.dumps(sorted(self.sample_numbers)),
            "carousel_numbers_json": json.dumps(sorted(self.carousel_numbers)),
            "run_mode_codes_json": json.dumps(sorted(self.run_mode_codes)),
            "time_min_unix_s": self.time_min_unix_s,
            "time_max_unix_s": self.time_max_unix_s,
            "elapsed_test_time_min_s": self.elapsed_min_s,
            "elapsed_test_time_max_s": self.elapsed_max_s,
            "physical_rows": self.physical_rows,
            "empty_rows": self.empty_rows,
            "malformed_rows": self.malformed_rows,
            "invalid_time_rows": self.invalid_time_rows,
            "sentinel_time_rows": self.sentinel_time_rows,
            "valid_rows": self.valid_rows,
            "issues_json": json.dumps(
                [issue.as_dict() for issue in self.issues], ensure_ascii=False
            ),
            "column_count": len(self.header),
            "channel_count": len(self.stats),
            "constant_channels_json": json.dumps(sorted(self.constant_channels), ensure_ascii=False),
            "sentinel_channels_json": json.dumps(sorted(self.sentinel_channels), ensure_ascii=False),
            "channel_profiles_json": json.dumps(self.channel_profiles(), ensure_ascii=False),
            "sha256": self.source.sha256,
            "retrieved_at": self.source.retrieved_at,
            "source_url": self.source.source_url,
            "parser_version": PARSER_VERSION,
            "notes": "SAME-R HKP housekeeping/telemetry run; not a flame-spread measurement.",
        }


def _read_rows(source: SourceFile) -> tuple[list[str], list[list[str]]]:
    with source.path.open("r", encoding="utf-8-sig", errors="strict", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"{source.path} is empty") from exc
        rows = [list(row) for row in reader]
    require_exact_header(header, SMOKE_HEADER, source)
    return header, rows


def scan_smoke(source: SourceFile) -> SmokeScan:
    header, rows = _read_rows(source)
    index = {name: position for position, name in enumerate(header)}
    stats = [
        SmokeChannelStats(
            raw_name=raw,
            canonical=SMOKE_CHANNELS[raw]["canonical"],
            unit=SMOKE_CHANNELS[raw]["unit"],
            uncalibrated=bool(SMOKE_CHANNELS[raw]["uncalibrated"]),
        )
        for raw in SMOKE_HEADER
        if raw not in EXCLUDED_CHANNELS
    ]
    scan = SmokeScan(source=source, header=header, stats=stats)

    for source_row, row in enumerate(rows, start=1):
        scan.physical_rows += 1
        if row_is_empty(row):
            scan.empty_rows += 1
            continue
        if len(row) != len(header):
            scan.malformed_rows += 1
            scan.issues.append(
                ParseIssue(
                    severity="warning",
                    code="row_shape",
                    message=(
                        f"row has {len(row)} fields but the exact header has {len(header)}; "
                        "the raw row is preserved in the parse report and is not emitted as points"
                    ),
                    source_row=source_row,
                    token=raw_row_json(header, row),
                )
            )
            continue
        parsed_time = parse_number(row[index["Time"]])
        if parsed_time.value is None:
            scan.invalid_time_rows += 1
            continue
        unix_time = int(parsed_time.value)
        if unix_time < 0:
            scan.sentinel_time_rows += 1
            continue
        scan.valid_rows += 1
        scan.time_min_unix_s = unix_time if scan.time_min_unix_s is None else min(scan.time_min_unix_s, unix_time)
        scan.time_max_unix_s = unix_time if scan.time_max_unix_s is None else max(scan.time_max_unix_s, unix_time)

        elapsed = parse_number(row[index["ElapsedTestTime(Secs)"]])
        if elapsed.value is not None:
            scan.elapsed_min_s = elapsed.value if scan.elapsed_min_s is None else min(scan.elapsed_min_s, elapsed.value)
            scan.elapsed_max_s = elapsed.value if scan.elapsed_max_s is None else max(scan.elapsed_max_s, elapsed.value)

        for name, target in (
            ("TestNumber", scan.test_numbers),
            ("SampleNumber", scan.sample_numbers),
            ("CarouselNumber", scan.carousel_numbers),
            ("RunMode", scan.run_mode_codes),
        ):
            parsed = parse_number(row[index[name]])
            if parsed.value is not None and parsed.value == int(parsed.value):
                target.add(int(parsed.value))

        for channel in stats:
            channel.observe(row[index[channel.raw_name]])

    return scan


def iter_smoke_points(scan: SmokeScan) -> Iterator[dict[str, Any]]:
    header, rows = _read_rows(scan.source)
    index = {name: position for position, name in enumerate(header)}
    constant = scan.constant_channels
    for source_row, row in enumerate(rows, start=1):
        if row_is_empty(row):
            continue
        if len(row) != len(header):
            continue
        parsed_time = parse_number(row[index["Time"]])
        if parsed_time.value is None or parsed_time.value < 0:
            continue
        unix_time = int(parsed_time.value)
        elapsed = parse_number(row[index["ElapsedTestTime(Secs)"]]).value
        source_time_string = row[index["TimeString"]].strip()
        for channel in scan.stats:
            raw_value = row[index[channel.raw_name]]
            parsed = parse_number(raw_value)
            raw = parsed.raw
            if raw is None or not str(raw).strip():
                continue
            if str(raw).strip() == "-999":
                value = None
                quality = "sentinel"
            elif parsed.value is None:
                value = None
                quality = (
                    "spreadsheet_error"
                    if parsed.flag == "spreadsheet_error"
                    else parsed.flag
                )
            else:
                value = parsed.value
                quality = "ok"
                if channel.raw_name in constant:
                    quality = "constant"
                elif channel.uncalibrated:
                    quality = "uncalibrated"
                elif channel.unit == "not stated":
                    quality = "not_stated_unit"
            yield {
                "observation_id": observation_id(
                    "PSI-101",
                    scan.source.file_name,
                    None,
                    source_row,
                    suffix=channel.raw_name,
                ),
                "run_id": scan.run_id,
                "accession": "PSI-101",
                "source_file": scan.source.file_name,
                "source_row": source_row,
                "unix_time_s": unix_time,
                "elapsed_test_time_s": elapsed,
                "source_time_string": source_time_string,
                "channel_name_raw": channel.raw_name,
                "channel_name_canonical": channel.canonical,
                "raw_value": raw,
                "value": value,
                "unit": channel.unit,
                "quality_flag": quality,
                "source_sha256": scan.source.sha256,
                "retrieved_at": scan.source.retrieved_at,
                "source_url": scan.source.source_url,
            }
