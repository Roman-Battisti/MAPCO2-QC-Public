# 3rd party libraries
import numpy as np


def seawater_density(temperature, sal, pressure):
    """Compute seawater density using UNESCO (1983)
    http://ocean.jfe-advantech.co.jp/english/sensor/img/density.pdf

    Parameters
    ------------
    temperature: array-like (deg C) with valid range 2 <= temperature <= 40
    sal: array-like (PSU) measured salinity with valid range 0 <= sal <= 42
    pressure: array-like (decibars) with valid range 0 <= pressure <= 10000

    Output
    ------------
    density: array-like (kg/m**3)
    """

    # Constants
    a0, a1, a2, a3, a4, a5 = (
        999.842594, 6.793952e-2, -9.095290e-3, 1.001685e-4, -1.120083e-6,
        6.536332e-9
    )
    b0, b1, b2, b3, b4 = (
        8.24493e-1, -4.0899e-3, 7.6438e-5, -8.2467e-7, 5.3875e-9
    )
    c0, c1, c2 = [-5.72466e-3, 1.0227e-4, -1.6546e-6]
    d0 = 4.8314e-4
    e0, e1, e2, e3, e4 = (
        19652.21, 148.4206, -2.327105, 1.360477e-2, -5.155288e-5
    )
    f0, f1, f2, f3 = [54.6746, -0.603459, 1.09987e-2, -6.1670e-5]
    g0, g1, g2 = [7.944e-2, 1.6483e-2, -5.3009e-4]
    h0, h1, h2, h3 = [3.239908, 1.43713e-3, 1.16092e-4, -5.77905e-7]
    i0, i1, i2 = [2.2838e-3, -1.0981e-5, -1.6078e-6]
    j0 = 1.91075e-4
    k0, k1, k2 = [8.50935e-5, -6.12293e-6, 5.2787e-8]
    m0, m1, m2 = [-9.9348e-7, 2.0816e-8, 9.1697e-10]

    temperature = remove_grossRange_outliers(temperature, 2, 40)
    sal = remove_grossRange_outliers(sal, 0, 42)
    pressure = remove_grossRange_outliers(pressure, 0, 10000)

    t = temperature * 1.00024
    p = pressure / 10

    rho_w = a0 + a1 * t + a2 * t ** 2 + a3 * t ** 3 + a4 * t ** 4 + a5 * t ** 5
    rho_s_t_0 = (
        rho_w
        + (b0 + b1 * t + b2 * t ** 2 + b3 * t ** 3 + b4 * t ** 4) * sal
        + (c0 + c1 * t + c2 * t ** 2) * sal ** (3 / 2)
        + d0 * sal ** 2
    )

    A_w = h0 + h1 * t + h2 * t ** 2 + h3 * t ** 3
    B_w = k0 + k1 * t + k2 * t ** 2
    A = A_w + (i0 + i1 * t + i2 * t ** 2) * sal + j0 * sal ** (3 / 2)
    B = B_w + (m0 + m1 * t + m2 * t ** 2) * sal
    K_w = e0 + e1 * t + e2 * t ** 2 + e3 * t ** 3 + e4 * t ** 4

    K_s_t_0 = (
        K_w
        + (f0 + f1 * t + f2 * t ** 2 + f3 * t ** 3) * sal
        + (g0 + g1 * t + g2 * t ** 2) * sal ** (3 / 2)
    )
    K_s_t_p = K_s_t_0 + A * p + B * p ** 2

    density = rho_s_t_0 / (1 - p / K_s_t_p)

    return density


def remove_grossRange_outliers(data, min_value, max_value):
    """
    Replaces data that lies outside of gross range with NaN. This avoids the
    RunTime warning associated with NaN values.

    Parameters
    ------------
    data: (array-like)
    min_value: (int or float) Minimum allowable value of data
    max_value: (int or float) Maximum allowable value of data
    """
    bad_data_index = (data[~np.isnan(data)] < min_value) | (data[~np.isnan(data)] > max_value)  # noqa : E501
    intermediate = data[~np.isnan(data)]
    intermediate[bad_data_index] = float('nan')
    data[~np.isnan(data)] = intermediate
    return data
