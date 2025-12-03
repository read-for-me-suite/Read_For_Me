# hardware/owon_decoder.py
"""
Décodage des trames 6 octets du multimètre OWON 16.

Ce module ne fait QUE :
- définir le mapping des fonctions (tension, courant, ohms, etc.),
- décoder les 6 octets en champs lisibles.

Aucun print, aucune I/O, aucune TTS.
"""

from dataclasses import dataclass
from typing import List

# Dictionnaire de description des fonctions du multimètre :
# type de mesure (Unité/mode AC-DC) codé sur 13 bits
OWON_FUNCTION = {
    "MILLI_VOLT_DC": 7683,
    "MILLI_VOLT_AC": 7691,
    "VOLT_DC": 7684,
    "VOLT_AC": 7692,
    "DIODE_TEST": 7764,
    "MICRO_AMPERE_DC": 7698,
    "MILLI_AMPERE_AC": 7699,
    "MICRO_AMPERE_AC": 7706,
    "MILLI_AMPERE_DC": 7707,
    "AMPERE_DC": 7700,
    "AMPERE_AC": 7708,
    "OHM_NORMAL": 7716,
    "CONTINUITY_TEST": 7772,
    "KILO_OHM": 7717,
    "MEGA_OHM": 7718,
    "NANO_FARAD": 7721,
    "MICRO_FARAD": 7722,
    "MILLI_FARAD": 7723,
    "FARAD": 7724,
    "HERTZ": 7732,
    "PERCENTAGE": 7740,
    "CELSIUS": 7748,
    "FAHRENHEIT": 7756,
    "NEAR_FIELD": 7788,
}


@dataclass
class OwonMultimeterData:
    """Représente une trame décodée du multimètre OWON 16."""

    raw_data: List[int]
    decimal_places: int
    overflow: int
    unit: int
    unit_name: str
    data_hold_mode: int
    relative_mode: int
    auto_ranging: int
    low_battery: int
    value: float
    sign: int

    @classmethod
    def from_raw(cls, raw_data: List[int]) -> "OwonMultimeterData":
        """Crée une instance à partir de 6 octets bruts."""
        if len(raw_data) != 6:
            raise ValueError(f"Expected 6 bytes of data, got {len(raw_data)}")

        # 2 premiers octets : décimales + code fonction
        unit_and_decimal = (raw_data[1] << 8) | raw_data[0]
        # octet 3 : flags divers
        flags = raw_data[2]
        # octets 5 et 6 : valeur + signe (little endian)
        value_and_sign = (raw_data[5] << 8) | raw_data[4]

        decimal_places = unit_and_decimal & 0b11
        overflow = (unit_and_decimal >> 2) & 0b1
        unit = unit_and_decimal >> 3  # 13 bits

        unit_name = cls._get_unit_from_value(unit)

        data_hold_mode = flags & 0b1
        relative_mode = (flags >> 1) & 0b1
        auto_ranging = (flags >> 2) & 0b1
        low_battery = (flags >> 3) & 0b1

        raw_value = value_and_sign & 0b11111111111111  # 15 bits ?
        sign = (value_and_sign >> 15) & 0b1

        if sign:
            raw_value = -raw_value

        scale_factor = 10 ** decimal_places
        value = raw_value / scale_factor

        return cls(
            raw_data=list(raw_data),
            decimal_places=decimal_places,
            overflow=overflow,
            unit=unit,
            unit_name=unit_name,
            data_hold_mode=data_hold_mode,
            relative_mode=relative_mode,
            auto_ranging=auto_ranging,
            low_battery=low_battery,
            value=value,
            sign=sign,
        )

    @staticmethod
    def _get_unit_from_value(code: int) -> str:
        """Renvoie un nom d'unité lisible à partir du code entier."""
        for key, val in OWON_FUNCTION.items():
            if val == code:
                return key.replace("_", " ")
        return "UNKNOWN"
