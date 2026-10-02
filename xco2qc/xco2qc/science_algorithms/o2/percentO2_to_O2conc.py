import numpy as np

from .CT_from_pt import CT_from_pt, strip_mask
from .SA_from_SP import SA_from_SP


def temp_to_scaledTemp(temperature):
    """
    convert T to scaled temperature T, 
     is a newly defined, scaled temperature: 
     T, = ln[(298.15 - t)(273.15 + t)-?1. 
     nificantly improves the rms deviation of the fit,
     particularly at high and low T and S. 
    """
    return np.log((298.15 - temperature) / (273.15 + temperature))


def concO2(temperature, a_S):
    """
    Estimated concentration of O2 from sea temperature at the sea surface.
    
    Parameters
    ------------
    :param temperature: (array-like) temperature
    :param a_S: (array-like) absolute salinity (see absoluteSalinity)
    
    Output
    ------------
    :output:  (array-like) scaled temperature
    
    Adapted from:
    O2sol   Solubility of O2 in sea water
    =========================================================================
     O2sol Version 1.1 4/4/2005
              Author: Roberta C. Hamme (Scripps Inst of Oceanography)     
     AUTHOR:  Roberta Hamme (rhamme@ucsd.edu)
    
     REFERENCE:
        Hernan E. Garcia and Louis I. Gordon, 1992.
        "Oxygen solubility in seawater: Better fitting equations"
        Limnology and Oceanography, 37, pp. 1307-1312.
    """
    
    # constants from Table 1 of Garcia & Gordon for the fit to Benson and Krause (1984)
    # umol/kg 
    A0_o2 = 5.80871
    A1_o2 = 3.20291
    A2_o2 = 4.17887
    A3_o2 = 5.10006
    A4_o2 = -9.86643e-2
    A5_o2 = 3.80369
    B0_o2 = -7.01577e-3
    B1_o2 = -7.70028e-3
    B2_o2 = -1.13864e-2
    B3_o2 = -9.51519e-3
    C0_o2 = -2.75915e-7

    s_T = temp_to_scaledTemp(temperature)

    # Corrected Eqn (8) of Garcia and Gordon 1992
    return np.exp(
        A0_o2
        + A1_o2 * s_T
        + A2_o2 * s_T ** 2
        + A3_o2 * s_T ** 3
        + A4_o2 * s_T ** 4
        + A5_o2 * s_T ** 5
        + a_S * (B0_o2 + B1_o2 * s_T + B2_o2 * s_T ** 2 + B3_o2 * s_T ** 3)
        + C0_o2 * a_S ** 2
    )


def percentO2_to_O2conc(o2_percent, sss, sst, lat, long, pressure):
    """
     Convert sea surface %O2 to concentration [umol/kg].
     Parameters
     ------------
     :param o2_percent: (array-like) scaled percent O2
     :param sss: (array-like) sea surface salinity [PSU]
     :param sst: (array-like) sea surface temperature [deg C]
     :param lat: (array-like) latitude (range -90 to 90) [deg]
     :param long: (array-like) longitude (range -180 to 180 or 0 to 360 decimal degrees East)
     :param pressure: (array-like) pressure [dbar]
     
     Output
     -----------
     :output: O2 in umol/kg
    """
    temp_S = temp_to_scaledTemp(sst)  # convert to scaled temperature
    a_S = SA_from_SP(sss, pressure, long, lat)  # convert to absolute salintiy
    
    ct = CT_from_pt(a_S, sst)  # conservative temperature from potential temperature [deg C]
    ct, mask = strip_mask(ct)
    sol_umolkg = concO2(ct, a_S)
    
    return np.ma.array((sol_umolkg * o2_percent), mask=mask, copy=False)
    
    

if __name__ == '__main__':
    # test
    percentO2 = np.array([0.89])
    sst = np.array([10])
    sss = np.array([35])
    long = np.array([30])
    lat = np.array([30])
    pressure = np.array([0.5])
    print(percentO2_to_O2conc(percentO2, sss, sst, lat, long, pressure))
    
