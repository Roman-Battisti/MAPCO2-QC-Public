# 3rd party library imports
import numpy as np


def calc_saturated_vapor_pressure(T, S):
    """
    Parameters
    ----------
    T : temperature in deg K
    S : salinity in PSU
    """
    p_sw = np.full(T.shape, np.nan)

    p_sw = np.exp(
        24.4543
        - (67.4509 * (100 / T))
        - (4.8489 * (np.log(T / 100)))
        - (0.000544 * S)
    )

    return p_sw


def calc_fugacity(P_hPa, T_cel, S, X1):
    """
    Parameters:
        p_hPa is in hPa, Temp in degC, Salinity in PSU, X1 is xCO2, all are
        masked numpy arrays
    """
    R = 82.056  # 82.056 cm3-atm/mole-K
    p_atm = P_hPa / 1013.25  # convert to pressure in atm

    # f = x1 * (p_atm - p_sw)*exp[p_atm(B + 2d)/RT]
    # x1 is the measured mole fraction of the analyte gas in dry air (ppm)
    #
    # p_atm is the total barometric pressure in the units of atmospheres
    #
    # p_sw is the saturated vapor pressure seawater (in atm) at the
    # temperature of the measurements and is calculated from equation (Weiss):_
    # ln p_sw = 24.4543 - (67.4509*(100/T)) - (4.8489*(ln(T/100))) - 0.000544S
    # where S is salinity in PSU

    T = T_cel + 273.15  # convert to Kelvin

    p_sw = calc_saturated_vapor_pressure(T, S)

    # B is the Virial Coefficient for CO2 and can be calculated using Weiss's
    # power series:
    # B = -1636.75 + (12.0408*T) - (3.27957 *10^-2 * T^2) +(3.16528*10^-5*T^3)
    b = (
        -1636.75
        + (12.0408 * T)
        - (3.27957 * 1e-2 * T ** 2)
        + (3.16528 * 1e-5 * T ** 3)
    )

    # d is the cross virial Coefficient B12 for interaction between gases 1 and
    # 2 minus the mean of B11 and B22 for 2 our gases
    # d = 57.7 - 0.118T cm3/mole
    D = 57.7 - 0.118 * T

    fugacity = (X1 * (p_atm - p_sw)) * np.exp(p_atm * (b + (2 * D)) / (R * T))
    return fugacity
