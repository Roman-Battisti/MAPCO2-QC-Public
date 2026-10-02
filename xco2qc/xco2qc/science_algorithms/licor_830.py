# 3rd party library imports
import numpy as np


class Licorv830(object):

    def __init__(self, config=None):

        self.config = config

        if self.config is None:
            self.a1 = 0.3989974
            self.a2 = 18.249359
            self.a3 = 0.097101984
            self.a4 = 1.8458913

            self.b1 = 1.10158
            self.b2 = -0.00612178
            self.b3 = -0.266278
            self.b4 = 3.69895

        else:
            self.a1 = self.config['licor_v830_coefficients']['a1']
            self.a2 = self.config['licor_v830_coefficients']['a2']
            self.a3 = self.config['licor_v830_coefficients']['a3']
            self.a4 = self.config['licor_v830_coefficients']['a4']

            self.b1 = self.config['licor_v830_coefficients']['b1']
            self.b2 = self.config['licor_v830_coefficients']['b2']
            self.b3 = self.config['licor_v830_coefficients']['b3']
            self.b4 = self.config['licor_v830_coefficients']['b4']

    def calc_xco2(self, zero_coeff, S0, S1, w, w0, p1, T):
        """
        The inputs could possibly be scalar, but we will force them to be
        vectorized.
        """

        # force arrays
        _zero_coeff = np.array(zero_coeff)
        _S0 = np.array(S0)
        _S1 = np.array(S1)
        _w = np.array(w)
        _w0 = np.array(w0)
        _p1 = np.array(p1)
        _T = np.array(T)
        xco2 = self._calc_licor830_vectorized(
            _zero_coeff, _S0, _S1, _w, _w0, _p1, _T
        )

        return xco2

    def _calc_licor830_vectorized(self, zero_coeff, S0, S1, w, w0, p1, T):

        # CO2 calibration function constants (from Israel's email)
        n = ((self.a2 * self.a3) + (self.a1 * self.a4))
        o = (self.a2 + self.a4)
        q = (self.a2 - self.a4)
        q_1 = (q ** 2)
        r = ((self.a2 * self.a3) + (self.a1 * self.a4))
        r_1 = (r ** 2)
        D = 2 * (self.a2 - self.a4) * ((self.a1 * self.a4) - (self.a2 * self.a3))  # noqa : E501

        z = self.a1 + self.a3

        p0 = 99  # po is std pressure, po = 99.0 kPa
        # p1 is the measured pressure
        # P is the ratio of the std pressure and measured press
        # whichever is > 1

        p = p1 / p0
        pif = p > 1

        if pif.any():
            p = p1 / p0
        else:
            p = p0 / p1

        # innerTerm is alphaC

        alphaC = (1 - ((w / w0) * zero_coeff))
        alphaCprime = (alphaC * S0) + ((alphaC ** 2) * S1)

        # compute some terms for the pressure correction function
        A = (1 / (self.b1 * (p - 1)))
        B = 1 / ((1 / (self.b2 + (self.b3 * p))) + self.b4)
        X = 1 + (1 / (A + (B * ((1 / (z - alphaC)) - (1 / z)))))
        # change whether alphaC or alphaCprime here

        # g is the empirical correction function and is a function of
        # absorptance and pressure
        if pif.any():
            g = 1 / X
        else:
            g = X

        # alphapc is the pressure corrected absorptance, alphaC'', and equal
        # absorptance(absp) * correction (g)
        alphapc = alphaCprime * g

        #    'F is the calibration polynomial

        numr = (
            (n - o * alphapc)
            - np.sqrt(q_1 * (alphapc ** 2) + D * alphapc + r_1)
        )
        denom = 2 * (alphapc - self.a1 - self.a3)

        F = numr / denom

        xco2 = F * ((T + 273.15))  # / (T0 + 273.15)) # added the bottom TO

        return xco2
