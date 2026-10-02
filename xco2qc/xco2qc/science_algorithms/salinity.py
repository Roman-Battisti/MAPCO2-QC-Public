"""
Use algorithm from

https://www.calcofi.com/index.php?option=com_content&view=article&id=445:ctd-data-algorithms
"""


import numpy as np


def calc_salinity(C, T, P):
    """
    C = conductivity S/m
    T = temperature deg C ITPS-68
    P = pressure in decibars
    """
    A1 = 2.070e-5
    A2 = -6.370e-10
    A3 = 3.989e-15
    B1 = 3.426e-2
    B2 = 4.464e-4
    B3 = 4.215e-1
    B4 = -3.107e-3
    C0 = 6.766097e-1
    C1 = 2.00564e-2
    C2 = 1.104259e-4
    C3 = -6.9698e-7
    C4 = 1.0031e-9

    # constants for salinity calculation
    a = np.array([0.0080, -0.1692, 25.3851, 14.0941, -7.0261, 2.7081])
    b = np.array([0.0005, -0.0056, -0.0066, -0.0375, 0.0636, -0.0144])

    # if C < 0
    C *= 10.0  # * convert Siemens/meter to mmhos/cm */
    R = C / 42.914
    val = 1 + B1 * T + B2 * T * T + B3 * R + B4 * R * T
    # if (val) RP = 1 + (P * (A1 + P * (A2 + P * A3))) / val;
    RP = 1 + (P * (A1 + P * (A2 + P * A3))) / val
    val = RP * (C0 + (T * (C1 + T * (C2 + T * (C3 + T * C4)))))
    # if (val) RT = R / val;
    RT = R / val
    # if (RT <= 0.0) RT = 0.000001;
    sum1 = sum2 = 0.0
    for i in range(6):
        temp = RT ** (i/2.0)
        sum1 += a[i] * temp
        sum2 += b[i] * temp

    val = 1.0 + 0.0162 * (T - 15.0)

    # if (val)
    result = sum1 + sum2 * (T - 15.0) / val
    # result = -99.;
    return result
