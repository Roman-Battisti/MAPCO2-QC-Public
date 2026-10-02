from .fugacity import calc_saturated_vapor_pressure


def calc_pco2(pressure, S, T, xco2):
    """
    """
    p_sw = calc_saturated_vapor_pressure(T, S)

    pco2 = (pressure / 101.325 - p_sw) * xco2
    return pco2
