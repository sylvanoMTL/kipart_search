# -*- coding: utf-8 -*-
#
# Engineering value normalisation (µF↔nF↔pF, kΩ↔Ω, mH↔µH)
#
# Vendored from: https://github.com/SchrodingersGat/KiBoM
# Original file: kibom/units.py
# License: MIT
# Original author: Oliver Henry Walters (@SchrodingersGat)
#
# This file is vendored (copied) with attribution rather than used as a
# git submodule, per project decision. See brainstorming session for rationale.

"""
Match and compare component values written in different formats.

Examples:
    0.1uF = 100n (different suffix, missing unit)
    0R1 = 0.1Ohm (unit replaces decimal, different units)
"""

from __future__ import unicode_literals
import re
import locale

PREFIX_MICRO = [u"μ", u"µ", "u", "micro"]
PREFIX_MILLI = ["milli", "m"]
PREFIX_NANO = ["nano", "n"]
PREFIX_PICO = ["pico", "p"]
PREFIX_KILO = ["kilo", "k"]
PREFIX_MEGA = ["mega", "meg", "M"]
PREFIX_GIGA = ["giga", "g"]

PREFIX_ALL = PREFIX_PICO + PREFIX_NANO + PREFIX_MICRO + PREFIX_MILLI + PREFIX_KILO + PREFIX_MEGA + PREFIX_GIGA

# Common methods of expressing component units
# Note: we match lowercase string, so both: Ω and Ω become the lowercase omega
UNIT_R = ["r", "ohms", "ohm", u'\u03c9']
UNIT_C = ["farad", "f"]
UNIT_L = ["henry", "h"]

UNIT_ALL = UNIT_R + UNIT_C + UNIT_L

# Compiled regex to match the values
match = None
# Current locale decimal point value
decimal_point = None


def getUnit(unit):
    """Return a simplified version of a units string, for comparison purposes."""
    if not unit:
        return None

    unit = unit.lower()

    if unit in UNIT_R:
        return "R"
    if unit in UNIT_C:
        return "F"
    if unit in UNIT_L:
        return "H"

    return None


def getPrefix(prefix):
    """Return the (numerical) value of a given prefix."""
    if not prefix:
        return 1

    # 'M' is mega, 'm' is milli
    if prefix != 'M':
        prefix = prefix.lower()

    if prefix in PREFIX_PICO:
        return 1.0e-12
    if prefix in PREFIX_NANO:
        return 1.0e-9
    if prefix in PREFIX_MICRO:
        return 1.0e-6
    if prefix in PREFIX_MILLI:
        return 1.0e-3
    if prefix in PREFIX_KILO:
        return 1.0e3
    if prefix in PREFIX_MEGA:
        return 1.0e6
    if prefix in PREFIX_GIGA:
        return 1.0e9

    return 1


def groupString(group):
    """Return a reg-ex string for a list of values."""
    return "|".join(group)


def matchString():
    return r"^([0-9\.]+)\s*(" + groupString(PREFIX_ALL) + ")*(" + groupString(UNIT_ALL) + r")*(\d*)$"


def compMatch(component):
    """
    Return a normalized value and units for a given component value string.

    e.g. compMatch('10R2') returns (10.2, 1, 'R')
    e.g. compMatch('3.3mOhm') returns (3.3, 0.001, 'R')
    """
    global decimal_point
    if not decimal_point:
        decimal_point = locale.localeconv()['decimal_point']
    if decimal_point and decimal_point != '.':
        component = component.replace(decimal_point, ".")

    component = component.strip().replace(",", "")

    global match
    if not match:
        match = re.compile(matchString(), flags=re.IGNORECASE)

    result = match.search(component)

    if not result:
        return None

    if not len(result.groups()) == 4:
        return None

    value, prefix, units, post = result.groups()

    # Special case where units is in the middle of the string
    # e.g. "0R05" for 0.05Ohm
    if post and "." not in value:
        try:
            value = float(int(value))
            postValue = float(int(post)) / (10 ** len(post))
            value = value * 1.0 + postValue
        except Exception:
            return None

    try:
        val = float(value)
    except Exception:
        return None

    return (val, getPrefix(prefix), getUnit(units))


def componentValue(valString):
    """Extract the numeric value from a component value string."""
    result = compMatch(valString)

    if not result:
        return valString

    if not len(result) == 2:
        return valString

    val = result[0]
    return val


def compareValues(c1, c2):
    """Compare two component values, accounting for different unit prefixes."""
    r1 = compMatch(c1)
    r2 = compMatch(c2)

    if not r1 or not r2:
        return False

    (v1, p1, u1) = r1
    (v2, p2, u2) = r2

    v1 = "{0:.15f}".format(v1 * 1.0 * p1)
    v2 = "{0:.15f}".format(v2 * 1.0 * p2)

    if v1 == v2:
        if u1 == u2:
            return True
        if not u1:
            return True
        if not u2:
            return True

    return False
