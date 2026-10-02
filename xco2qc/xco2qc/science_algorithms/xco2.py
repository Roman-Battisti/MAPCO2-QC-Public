# 3rd party library imports
import numpy as np

# local imports
from .vapor_pressure import calculate_vapor_pressure


def calc_xco2(T, p1, v, vo, zerocoeff, spancoeff):
    """
    Parameters
    ----------
    T : ndarray
        temperature
    p1 : ndarray
        pressure
    v, vo : ndarray
        LICOR voltages (raw1 and raw2)
    zerocoeff, spancoeff : ndarray
        TODO
    """

    C1 = 439.7123
    C2 = 1255.133
    C3 = 27189.37
    C4 = -160374.6
    c5 = 570291
    c6 = -604330.8
    a = 1.10158
    b = -0.00612178
    C = -0.266278
    d = 3.69895
    Z = 0.5
    t_std = 50

    # standard pressure
    po = 99

    # if p1 < po:
    #     P = po / p1
    # elif p1 > po:
    #     P = p1 / po
    # else:
    #     P = p1
    #
    # P is the ratio of the std pressure and measured press
    P = np.where(p1 < po, po / p1, p1 / po)

    absp = (1 - ((v / vo) * zerocoeff)) * spancoeff

    # g is the empirical correction function and is a function of absorptance
    # and pressure
    a_1 = (1 / (a * (P - 1)))
    b_1 = 1 / ((1 / (b + (C * P)) + d))
    x = 1 + (1 / (a_1 + (b_1 * ((1 / (Z - absp)) - (1 / Z)))))

    # if p1 == po:
    #     g = 1
    # elif p1 < po:
    #     g = x
    # elif p1 > po:
    #     g = 1 / x
    g = np.where(p1 < po, x, 1 / x)

    # s is the pressure corrected absorptance and equal to
    # absorptance(absp) * correction (g)
    s = absp * g

    # f is the calibration polynomial
    F = (C1 * s) + (C2 * s ** 2) + (C3 * s ** 3) + (C4 * s ** 4) + (c5 * s ** 5) + (c6 * s ** 6)  # noqa : E501

    xco2 = 10 * F * ((T + 273) / (t_std + 273))
    return xco2


def calc_dry_xco2(rh_temp, rh_equil, rh, temp, xco2_wet, press):

    vapor_pressure = calculate_vapor_pressure(rh_temp, rh_equil, rh)

    xco2_dry = xco2_wet / ((press - vapor_pressure) / press)
    return xco2_dry


def calc_xco2_licor_v2(T, p1, w, w0, zerocoeff, S0, S1):
    """
    Parameters
    ----------
    T : ndarray
        temperature
    p1 : ndarray
        pressure
    w, w0 : ndarray
        LICOR voltages (raw1 and raw2)
    zerocoeff :
        TODO
    S0, S1 : ndarray
        The span coefficients.
    """
    # CO2 calibration function constants
    a1 = 0.3989974
    a2 = 5897.2804
    a3 = 0.097101982
    a4 = 596.49981
    a = a2 - a4
    b = 2 * a * (a1 * a4 - a2 * a3)
    D = a3 * a2 + a1 * a4

    # constants to compute X
    b1 = 1.10158
    b2 = -0.00612178
    b3 = -0.266278
    b4 = 3.69895
    b5 = 0.49609938

    t_std = 50
    po = 99

    # p1 is the measured pressure
    # po is std pressure, po = 99.0 kPa
    # P is the ratio of the std pressure and measured press whichever is > 1
    P = np.where(p1 < po, po / p1, p1 / po)

    innerTerm = (1 - ((w / w0) * zerocoeff))
    # Eq 4-3
    absp = (innerTerm * S0) + (innerTerm ** 2) * S1

    # compute some terms for the pressure correction function
    a_1 = (1 / (b1 * (P - 1)))
    b_1 = 1 / ((1 / (b2 + (b3 * P)) + b4))
    x = 1 + (1 / (a_1 + (b_1 * ((1 / (b5 - absp)) - (1 / b5)))))

    # g is the empirical correction function and is a function of absorptance
    # and pressure
    # if p1 == po:
    #     g = 1
    # elif p1 < po:
    #     g = x
    # elif p1 > po:
    #     g = 1 / x
    g = np.where(p1 < po, x, 1 / x)

    # alphapc is the pressure corrected absorptance and equal
    # absorptance(absp) * correction (g)
    alphapc = absp * g

    # F is the calibration polynomial
    numr = (
        (D - (a2 + a4) * alphapc)
        - np.sqrt(a ** 2 * alphapc ** 2 + b * alphapc + D ** 2)
    )
    denom = 2 * (alphapc - a1 - a3)

    F = numr / denom

    xco2 = F * ((T + 273) / (t_std + 273))
    return xco2
