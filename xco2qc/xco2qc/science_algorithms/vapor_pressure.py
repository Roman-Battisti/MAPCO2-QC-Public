# 3rd party library imports
import numpy as np


def calculate_vapor_pressure(rh_temp, rh_equil, rh):
    """
    Parameters
    ----------
    rh_temp, rh_equil, rh : ndarray

    Returns
    -------
    vapor_pressure : ndarray
    """
    saturation_vapor_pressure = (
        0.61365 * np.exp((17.502 * rh_temp) / (240.97 + rh_temp))
    )
    vapor_pressure = (rh_equil - rh) * saturation_vapor_pressure / 100

    return vapor_pressure
