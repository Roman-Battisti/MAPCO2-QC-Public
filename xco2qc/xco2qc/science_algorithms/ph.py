# 3rd party library imports
from PyCO2SYS.api import CO2SYS_wrap as co2sys


def calc_ph_pco2sys(alk, sal, temp_in, pco2):

    df1 = co2sys(alk=alk, pco2=pco2, sal=sal, temp_in=temp_in, pres_in=0.5)

    return df1['pHin']
