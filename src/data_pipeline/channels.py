"""Explicit channel mapping for PSI-100 SAFFIRE-III telemetry.

The mapping is deliberately conservative. A canonical name is assigned only
when the inspected source header or the verified XLSX human-readable header
supports it. Units are recorded only when stated or unambiguously encoded in
the source header. Everything else is ``not stated``.

The raw CSV and the workbook use different header spellings for the same
channels. Both spellings are mapped here so that the long telemetry table
keeps the exact source name in ``channel_name_raw`` while exposing a stable
canonical name.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChannelDefinition:
    canonical: str
    unit: str
    uncalibrated: bool = False
    note: str = ""


# Raw CSV signal names, verified against the downloaded 47-column export.
_CSV_CHANNELS: dict[str, ChannelDefinition] = {
    "RelativeSeconds": ChannelDefinition("relative_time_ms", "ms", note="Milliseconds despite the header name."),
    "CygnusTimestamp": ChannelDefinition("cygnus_timestamp_ms", "Unix epoch ms"),
    "SaffireTimestamp": ChannelDefinition("saffire_timestamp_raw", "not stated"),
    "P@sfsHk.Radiometer1value": ChannelDefinition("radiometer_1_raw", "not stated", True, "Relative radiometer output."),
    "P@sfsHk.Radiometer2value": ChannelDefinition("radiometer_2_raw", "not stated", True, "Relative radiometer output."),
    "P@sfsHk.Radiometer3value": ChannelDefinition("radiometer_3_raw", "not stated", True, "Relative radiometer output."),
    "P@sfsHk.Radiometer4value": ChannelDefinition("radiometer_4_raw", "not stated", True, "Relative radiometer output."),
    "P@sfsHk.Anemometer1": ChannelDefinition("anemometer_1_raw", "not stated", True, "Raw anemometer output."),
    "P@sfsHk.Anemometer2": ChannelDefinition("anemometer_2_raw", "not stated", True, "Raw anemometer output."),
    "P@sfsHk.FanTachometer": ChannelDefinition("fan_tachometer_raw", "not stated", True, "Do not assume rpm."),
    "P@sfsHk.SmokeWireVoltage": ChannelDefinition("smoke_wire_voltage_raw", "not stated", True),
    "P@sfsHk.SmokeWireCurrent": ChannelDefinition("smoke_wire_current_raw", "not stated", True),
    "P@PCM_ETS_TEMP_SIG": ChannelDefinition("pcm_air_temp_c", "°C"),
    "P@F1PCM_AIR_PRES_EPS1_SIG_POS": ChannelDefinition("pcm_pressure_eps1_psi", "psi"),
    "P@F2PCM_AIR_PRES_EPS2_SIG_POS": ChannelDefinition("pcm_pressure_eps2_psi", "psi"),
    "P@F3PCM_AIR_PRES_EPS3_SIG_POS": ChannelDefinition("pcm_pressure_eps3_psi", "psi"),
    "P@OPS_PCM_PRES_AVG_BY_TEMP": ChannelDefinition("pcm_pressure_temp_psi_k", "psi/K", note="Composite channel; do not split."),
    "P@CDH_F1PCM_SMK_DET_OBS_SENS_P": ChannelDefinition("fiz1_smoke_obscuration_v", "V", True),
    "P@CDH_F2PCM_SMK_DET_OBS_SENS_P": ChannelDefinition("fiz2_smoke_obscuration_v", "V", True),
    "P@CDH_F1PCM_SMK_DET_SCAT_SENS_P": ChannelDefinition("fiz1_smoke_scatter_v", "V", True),
    "P@CDH_F2PCM_SMK_DET_SCAT_SENS_P": ChannelDefinition("fiz2_smoke_scatter_v", "V", True),
    "P@CDH_F1PCM_ECLS_FAN_PRESSURE_P": ChannelDefinition("fiz1_cabin_fan_delta_p_pa", "Pa"),
    "P@CDH_F2PCM_ECLS_FAN_PRESSURE_P": ChannelDefinition("fiz2_cabin_fan_delta_p_pa", "Pa"),
    "P@GNCAttitudeNavigatorShared.omegaEst_bdy.elements[0]": ChannelDefinition("body_rate_x_rad_s", "rad/s"),
    "P@GNCAttitudeNavigatorShared.omegaEst_bdy.elements[1]": ChannelDefinition("body_rate_y_rad_s", "rad/s"),
    "P@GNCAttitudeNavigatorShared.omegaEst_bdy.elements[2]": ChannelDefinition("body_rate_z_rad_s", "rad/s"),
    "P@GNCImuSensor.imu[0].currentMeas_Bdy.acc.elements[0]": ChannelDefinition("acceleration_x_m_s2", "m/s²"),
    "P@GNCImuSensor.imu[0].currentMeas_Bdy.acc.elements[1]": ChannelDefinition("acceleration_y_m_s2", "m/s²"),
    "P@GNCImuSensor.imu[0].currentMeas_Bdy.acc.elements[2]": ChannelDefinition("acceleration_z_m_s2", "m/s²"),
}

# Nine igniter voltage/current pairs share one pattern.
for _index in range(1, 10):
    _CSV_CHANNELS[f"P@sfsHk.Sample{_index}IgniterVoltage"] = ChannelDefinition(
        f"igniter_{_index}_voltage_raw", "not stated", True
    )
    _CSV_CHANNELS[f"P@sfsHk.Sample{_index}IgniterCurrent"] = ChannelDefinition(
        f"igniter_{_index}_current_raw", "not stated", True
    )


# Human-readable workbook headers, verified against the downloaded XLSX.
_XLSX_CHANNELS: dict[str, ChannelDefinition] = {
    "RelativeSeconds": ChannelDefinition("relative_time_ms", "ms"),
    "CygnusTimestamp": ChannelDefinition("cygnus_timestamp_ms", "Unix epoch ms"),
    "SaffireTimestamp": ChannelDefinition("saffire_timestamp_raw", "not stated"),
    "Cyg-Saf TS (ms)": ChannelDefinition("cygnus_minus_saffire_ms", "ms"),
    "Radiometer1Value": ChannelDefinition("radiometer_1_raw", "not stated", True),
    "Radiometer2Value": ChannelDefinition("radiometer_2_raw", "not stated", True),
    "Radiometer3Value": ChannelDefinition("radiometer_3_raw", "not stated", True),
    "Radiometer4Value": ChannelDefinition("radiometer_4_raw", "not stated", True),
    "Anemometer1": ChannelDefinition("anemometer_1_raw", "not stated", True),
    "Anemometer2": ChannelDefinition("anemometer_2_raw", "not stated", True),
    "FanTachometer": ChannelDefinition("fan_tachometer_raw", "not stated", True),
    "SmokeWireV": ChannelDefinition("smoke_wire_voltage_raw", "not stated", True),
    "SmokeWireI": ChannelDefinition("smoke_wire_current_raw", "not stated", True),
    "PCM Air Temp (degC)": ChannelDefinition("pcm_air_temp_c", "°C"),
    "PCM Press EPS1 (psi)": ChannelDefinition("pcm_pressure_eps1_psi", "psi"),
    "PCM Press EPS2 (Psi)": ChannelDefinition("pcm_pressure_eps2_psi", "psi"),
    "PCM Press EPS3 (PSI)": ChannelDefinition("pcm_pressure_eps3_psi", "psi"),
    "PCM Press EPS 1 (psi)": ChannelDefinition("pcm_pressure_eps1_psi", "psi"),
    "PCM Press ECM 2 (psi)": ChannelDefinition("pcm_pressure_ecm2_psi", "psi", note="Source spells ECM; preserved as published."),
    "PCM Press EPS 3 (psi)": ChannelDefinition("pcm_pressure_eps3_psi", "psi"),
    "PCM Press/Temp (psi/K)": ChannelDefinition("pcm_pressure_temp_psi_k", "psi/K"),
    "FIZ1 Smoke Detector Obscuration  (V)": ChannelDefinition("fiz1_smoke_obscuration_v", "V", True),
    "FIZ 2 Smoke Detector Obscuration (V)": ChannelDefinition("fiz2_smoke_obscuration_v", "V", True),
    "FIZ 1 Smoke Detector Scatterometer (V)": ChannelDefinition("fiz1_smoke_scatter_v", "V", True),
    "FIZ 2 Smoke Detector Scatterometer (V)": ChannelDefinition("fiz2_smoke_scatter_v", "V", True),
    "FIZ 1 Cabin Fan delta P (Pa)": ChannelDefinition("fiz1_cabin_fan_delta_p_pa", "Pa"),
    "FIZ 2 Cabin Fan Delta P (Pa)": ChannelDefinition("fiz2_cabin_fan_delta_p_pa", "Pa"),
    "body rate x axis (rad/s)": ChannelDefinition("body_rate_x_rad_s", "rad/s"),
    "body rate y axis (rad/s)": ChannelDefinition("body_rate_y_rad_s", "rad/s"),
    "body rate z axis (rad/s)": ChannelDefinition("body_rate_z_rad_s", "rad/s"),
    "acceleration x axis (m/s^2)": ChannelDefinition("acceleration_x_m_s2", "m/s²"),
    "acceleration y axis (m/s^2)": ChannelDefinition("acceleration_y_m_s2", "m/s²"),
    "acceleration z axis (m/s^2)": ChannelDefinition("acceleration_z_m_s2", "m/s²"),
    "Saffire Repeat?": ChannelDefinition("saffire_repeat_flag", "not stated"),
    "Row to Row Delta T (ms)": ChannelDefinition("row_to_row_delta_t_ms", "ms"),
    "delta timestamp (ms)": ChannelDefinition("saffire_delta_timestamp_ms", "ms"),
    "Relative Time (ms)": ChannelDefinition("relative_time_ms", "ms"),
    "Relative Time (s)": ChannelDefinition("relative_time_s", "s"),
    "Rel-to-Cygnus Time (s)": ChannelDefinition("rel_to_cygnus_time_s", "s"),
    "Tach/100": ChannelDefinition("fan_tachometer_div_100_raw", "not stated", True),
    "Cygnus-Saffire Time Stamp (ms)": ChannelDefinition("cygnus_minus_saffire_ms", "ms"),
    "Saffire timestamp row-to-row delta t (ms)": ChannelDefinition("saffire_row_to_row_delta_t_ms", "ms"),
}

for _index in range(1, 10):
    _XLSX_CHANNELS[f"Sample{_index}IgniterV"] = ChannelDefinition(
        f"igniter_{_index}_voltage_raw", "not stated", True
    )
    _XLSX_CHANNELS[f"Sample{_index}IgniterI"] = ChannelDefinition(
        f"igniter_{_index}_current_raw", "not stated", True
    )


CHANNEL_MAP: dict[str, ChannelDefinition] = {**_CSV_CHANNELS, **_XLSX_CHANNELS}


def channel_definition(raw_name: str) -> ChannelDefinition:
    """Return the explicit mapping or a conservative fallback.

    An unmapped header is not guessed into a scientific quantity. It keeps a
    slugged name, ``not stated`` unit, and is treated as uncalibrated.
    """

    mapped = CHANNEL_MAP.get(raw_name)
    if mapped is not None:
        return mapped
    slug = "".join(
        character.lower() if character.isalnum() else "_" for character in raw_name
    ).strip("_")
    return ChannelDefinition(slug or "unnamed_channel", "not stated", True, "Unmapped source header.")
