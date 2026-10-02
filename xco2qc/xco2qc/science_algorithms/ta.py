# 3rd party library imports
import numpy as np


def compute_ta(sss, sst, longitude, region=None):

    return _FUNCS[region](sss, sst, longitude)


def compute_ta_washington_state(sss, sst, longitude):
    """
    Washington State coast and Puget Sound (Fassbender et al. 2016a)
    """
    return 47.7 * sss + 647


def compute_ta_california_current_ecosystem(sss, sst, longitude):
    """
    California Current Ecosystem (Cullison Gray et al. 2011)
    """
    return 2131 + 50.8 * (sss - 31.25)


def cce1(sss, sst, longitude):
    """
    Station CCE1 in the California Current Ecosystem (Frazao per comm)
    TA uncertainty: 5
    """
    return 48.4057 * (sss - 33.23) + 2236.9


def cce2(sss, ssst, longitude):
    """
    Station CCE2 in the California Current Ecosystem (Frazao per comm)
    TA uncertainty: 5
    """
    return 50.5307 * (sss - 33.56) + 2238.2


def compute_ta_south_atlantic_bight(sss, sst, longitude):
    """
    South Atlantic Bight (Xue et al. 2006)
    """
    return 49.66 * sss + 573.63


def compute_ta_gulf_of_maine(sss, sst, longitude):
    """
    Gulf of Maine (Hunt, University of New Hampshire, personal communication)
    """
    return sss * 52.5 + 476


def compute_ta_kuroshio_extension(sss, sst, longitude):
    """
    Kuroshio Extension (Fassbender et al. 2017)
    """
    return sss * 63 + 75


def compute_ta_northeast_pacific(sss, sst, longitude):
    """
    Northeast Pacific (Fassbender et al. 2016b)
    """
    return sss * 37 + 988


def compute_ta_north_atlantic(sss, sst, longitude):
    """
    North Atlantic 30N - 80N (Lee et al. 2006)

    When sst > 20, use the subtropics equation.
    """
    ta = np.where(
        sst > 20,
        _compute_ta_subtropics(sss, sst, longitude),
        _compute_ta_north_atlantic(sss, sst, longitude),
    )
    return ta


def _compute_ta_north_atlantic(sss, sst, longitude):
    """
    North Atlantic 30N - 80N (Lee et al. 2006)
    """
    return (
        2305
        + 53.97 * (sss - 35)
        + 2.74 * (sss - 35) ** 2
        - 1.16 * (sst - 20)
        - 0.040 * (sst - 20) ** 2
    )


def compute_ta_north_pacific(sss, sst, longitude):
    """
    North Pacific ≥ 30N (Lee et al. 2006)

    Longitude MUST be positive, 0<= longitude < 360.  Use subtropics if SST >
    20.
    """
    return np.where(
        sst <= 20,
        _compute_ta_north_pacific(sss, sst, longitude),
        _compute_ta_subtropics(sss, sst, longitude)
    )


def _compute_ta_north_pacific(sss, sst, longitude):
    """
    North Pacific ≥ 30N (Lee et al. 2006)

    Longitude MUST be positive, 0<= longitude < 360
    """
    return (
        2305
        + 53.23 * (sss - 35)
        + 1.85 * (sss - 35) ** 2
        - 14.72 * (sst - 20)
        - 0.158 * (sst - 20) ** 2
        + 0.062 * (sst - 20) * (longitude % 360)
    )


def compute_ta_subtropics_atlantic(sss, sst, longitude):
    """
    Subtropics

    Atlantic 30S - 30N (Lee et al. 2006)
    Pacific 30S - 30N (Lee et al. 2006)
    Indian <= 30S (Lee et al. 2006)
    """
    return np.where(
        sst < 20,
        compute_ta_north_atlantic(sss, sst, longitude),
        _compute_ta_subtropics_atlantic(sss, sst, longitude)
    )


def _compute_ta_subtropics_atlantic(sss, sst, longitude):
    """
    Subtropics

    Atlantic 30S - 30N (Lee et al. 2006)
    Pacific 30S - 30N (Lee et al. 2006)
    Indian <= 30S (Lee et al. 2006)
    """
    return _compute_ta_subtropics(sss, sst, longitude)


def compute_ta_subtropics_pacific(sss, sst, longitude):
    """
    Subtropics

    Pacific 30S - 30N (Lee et al. 2006)
    """
    return np.where(
        sst < 20,
        compute_ta_north_pacific(sss, sst, longitude),
        _compute_ta_subtropics_pacific(sss, sst, longitude)
    )


def _compute_ta_subtropics_pacific(sss, sst, longitude):
    """
    Subtropics

    Atlantic 30S - 30N (Lee et al. 2006)
    """
    return _compute_ta_subtropics(sss, sst, longitude)


def compute_ta_subtropics_indian(sss, sst, longitude):
    """
    Subtropics

    Atlantic 30S - 30N (Lee et al. 2006)
    Pacific 30S - 30N (Lee et al. 2006)
    Indian <= 30S (Lee et al. 2006)
    """
    return np.where(
        sst < 20,
        compute_ta_southern_ocean(sss, sst, longitude),
        _compute_ta_subtropics(sss, sst, longitude)
    )


def _compute_ta_subtropics(sss, sst, longitude):
    """
    Subtropics

    Atlantic 30S - 30N (Lee et al. 2006)
    Pacific 30S - 30N (Lee et al. 2006)
    Indian <= 30S (Lee et al. 2006)
    """
    return (
        2305
        + 58.66 * (sss - 35)
        + 2.32 * (sss - 35) ** 2
        - 1.41 * (sst - 20)
        + 0.040 * (sst - 20) ** 2
    )


def compute_ta_eastern_pacific_upwelling(sss, sst, longitude):
    """
    Eastern Equatorial upwelling Pacific 75W - 110W, 20S - 20N
    (Lee et al. 2006)
    """
    return np.where(
        sst < 18,
        _compute_ta_subtropics_pacific(sss, sst, longitude),
        compute_ta_pacific_upwelling(sss, sst, longitude)
    )


def compute_ta_central_pacific_upwelling(sss, sst, longitude):
    """
    Central Equatorial upwelling Pacific 110W - 140W, 10S - 10N
    (Lee et al. 2006)
    """
    return np.where(
        sst < 18,
        _compute_ta_subtropics_pacific(sss, sst, longitude),
        compute_ta_pacific_upwelling(sss, sst, longitude)
    )


def compute_ta_pacific_upwelling(sss, sst, longitude):
    """
    Eastern Equatorial upwelling Pacific 75W - 110W, 20S - 20N
    (Lee et al. 2006)

    Central Equatorial upwelling Pacific 110W - 140W, 10S - 10N
    (Lee et al. 2006)
    """
    return (
        2294
        + 64.88 * (sss - 35)
        + 0.39 * (sss - 35) ** 2
        - 4.52 * (sst - 29)
        - 0.232 * (sst - 29) ** 2
    )


def compute_ta_pacific_upwelling_not_eastern_central(
    sss, sst, longitude
):
    """
    Equatorial Pacific outside of previous two categories (Lee et al. 2006)
    """
    return (
        2305
        + 58.66 * (sss - 35)
        + 2.32 * (sss - 35) ** 2
        - 1.41 * (sst - 20)
        + 0.040 * (sst - 20) ** 2
    )


def compute_ta_southern_ocean(sss, sst, longitude):
    """
    Southern Ocean 30S - 70S (Lee et al. 2006)
    """
    return np.where(
        sst > 20,
        _compute_ta_subtropics(sss, sst, longitude),
        _compute_ta_southern_ocean(sss, sst, longitude)
    )


def _compute_ta_southern_ocean(sss, sst, longitude):
    """
    Southern Ocean 30S - 70S (Lee et al. 2006)
    """
    return (
        2305
        + 52.48 * (sss - 35)
        + 2.85 * (sss - 35) ** 2
        - 0.49 * (sst - 20)
        + 0.086 * (sst - 20) ** 2
    )


_FUNCS = {
    1: compute_ta_washington_state,
    2: compute_ta_california_current_ecosystem,
    3: compute_ta_south_atlantic_bight,
    4: compute_ta_gulf_of_maine,
    5: compute_ta_kuroshio_extension,
    6: compute_ta_northeast_pacific,
    7: compute_ta_north_atlantic,
    8: compute_ta_north_pacific,
    9: compute_ta_subtropics_atlantic,
    10: compute_ta_subtropics_pacific,
    11: compute_ta_subtropics_indian,
    12: compute_ta_eastern_pacific_upwelling,
    13: compute_ta_central_pacific_upwelling,
    14: compute_ta_pacific_upwelling_not_eastern_central,
    15: compute_ta_southern_ocean,
    16: cce1,
    17: cce2,
}
