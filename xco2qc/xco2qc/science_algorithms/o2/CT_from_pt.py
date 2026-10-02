## code pulled from: https://github.com/TEOS-10/python-gsw/blob/master/gsw/utilities/utilities.py
## and from: https://github.com/TEOS-10/python-gsw/blob/master/gsw/gibbs/conversions.py

import numpy as np


## Constants ##
cp0 = 3991.86795711963
"""
The "specific heat" for use with Conservative Temperature. cp0 is the ratio
of potential enthalpy to Conservative Temperature.
See Eqn. (3.3.3) and Table D.5 from IOC et al. (2010).
"""
# from: https://github.com/TEOS-10/python-gsw/blob/master/gsw/gibbs/constants.py
##

sfac = 0.0248826675584615
"""
sfac = 1 / (40 * uPS) = 1 / (40. * (SSO / 35.))
"""


def strip_mask(*args):
    """
    Process the standard arguments for efficient calculation.
    Return unmasked arguments, plus a mask.
    The first argument, SA, is handled specially so that it can be
    This could be absorbed into a decorator, but it would
    require redefining functions to take the additional
    mask argument or kwarg.
    """
    mask = np.ma.getmaskarray(args[-1])
    SA = args[0]
    if SA.shape:
        SA = np.ma.asarray(SA)
        SA[SA < 0] = np.ma.masked
        for a in args[:-1]:
            mask = np.ma.mask_or(mask, np.ma.getmask(a))
        newargs = [SA.filled(0)]
    elif SA < 0:
        SA = 0
        for a in args[1:-1]:
            mask = np.ma.mask_or(mask, np.ma.getmask(a))
        newargs = [SA]
    newargs.extend([np.ma.filled(a, 0) for a in args[1:]])
    newargs.append(mask)
    return newargs


def pot_enthalpy_from_pt(SA, pt):
    """
    Calculates the potential enthalpy of seawater from potential
    temperature (whose reference sea pressure is zero dbar).
    Parameters
    ----------
    SA : array_like
         Absolute salinity [g kg :sup:`-1`]
    pt : array_like
         potential temperature referenced to a sea pressure of zero dbar
         [:math:`^\circ` C (ITS-90)]
    Returns
    -------
    pot_enthalpy : array_like
                   potential enthalpy [J kg :sup:`-1`]
    Notes
    -----
    TODO
    Examples
    --------
    >>> import gsw
    >>> SA = [34.7118, 34.8915, 35.0256, 34.8472, 34.7366, 34.7324]
    >>> pt = [28.7832, 28.4209, 22.7850, 10.2305, 6.8292, 4.3245]
    >>> gsw.pot_enthalpy_from_pt(SA, pt)
    array([ 115005.40853458,  113525.30870246,   90959.68769935,
             40821.50280454,   27253.21472227,   17259.10131183])
    References
    ----------
    .. [1] IOC, SCOR and IAPSO, 2010: The international thermodynamic equation
       of seawater - 2010: Calculation and use of thermodynamic properties.
       Intergovernmental Oceanographic Commission, Manuals and Guides No. 56,
       UNESCO (English), 196 pp. See section 3.2.
    """

    SA, pt, mask = strip_mask(SA, pt)

    SA = np.maximum(SA, 0)

    x2 = sfac * SA
    x = np.sqrt(x2)
    y = pt * 0.025  # Normalize for F03 and F08

    pot_enthalpy = (61.01362420681071 + y * (168776.46138048015 +
    y * (-2735.2785605119625 + y * (2574.2164453821433 +
    y * (-1536.6644434977543 + y * (545.7340497931629 +
    (-50.91091728474331 - 18.30489878927802 * y) * y))))) +
    x2 * (268.5520265845071 + y * (-12019.028203559312 +
    y * (3734.858026725145 + y * (-2046.7671145057618 +
    y * (465.28655623826234 + (-0.6370820302376359 -
    10.650848542359153 * y) * y)))) +
    x * (937.2099110620707 + y * (588.1802812170108 +
    y * (248.39476522971285 + (-3.871557904936333 -
    2.6268019854268356 * y) * y)) +
    x * (-1687.914374187449 + x * (246.9598888781377 +
    x * (123.59576582457964 - 48.5891069025409 * x)) +
    y * (936.3206544460336 +
    y * (-942.7827304544439 + y * (369.4389437509002 +
    (-33.83664947895248 - 9.987880382780322 * y) * y)))))))

    # The above polynomial for pot_enthalpy is the full expression for
    # potential enthalpy in terms of SA and pt, obtained from the Gibbs function
    # as below.  It has simply collected like powers of x and y so that it is
    # computationally faster than calling the Gibbs function twice as is done in
    # the commented code below. When this code below is run, the results are
    # identical to calculating pot_enthalpy as above, to machine precision.

    # g000 = gibbs(n0, n0, n0, SA, pt, 0)
    # g010 = gibbs(n0, n1, n0, SA, pt, 0)
    # pot_enthalpy = g000 - (Kelvin + pt) * g010

    # This is the end of the alternative code
    # %timeit gsw.CT_from_pt(SA, pt)
    # 1000 loops, best of 3: 1.34 ms per loop <- calling gibbs
    # 1000 loops, best of 3: 254 us per loop <- standard

    return np.ma.array(pot_enthalpy, mask=mask, copy=False)



def CT_from_pt(SA, pt):
    """
    Calculates Conservative Temperature of seawater from potential
    temperature (whose reference sea pressure is zero dbar).
    Parameters
    ----------
    SA : array_like
         Absolute salinity [g kg :sup:`-1`]
    pt : array_like
         potential temperature referenced to a sea pressure of zero dbar
         [:math:`^\circ` C (ITS-90)]
    Returns
    -------
    CT : array_like
         Conservative Temperature [:math:`^\circ` C (ITS-90)]
    Examples
    --------
    >>> import gsw
    >>> SA = [34.7118, 34.8915, 35.0256, 34.8472, 34.7366, 34.7324]
    >>> pt = [28.7832, 28.4209, 22.7850, 10.2305, 6.8292, 4.3245]
    >>> gsw.CT_from_pt(SA, pt)
    array([ 28.80992302,  28.43914426,  22.78624661,  10.22616561,
             6.82718342,   4.32356518])
    References
    ----------
    .. [1] IOC, SCOR and IAPSO, 2010: The international thermodynamic equation
       of seawater - 2010: Calculation and use of thermodynamic properties.
       Intergovernmental Oceanographic Commission, Manuals and Guides No. 56,
       UNESCO (English), 196 pp. See section 3.3.
    """

    SA, pt, mask = strip_mask(SA, pt)

    pot_enthalpy = pot_enthalpy_from_pt(SA, pt)

    CT = pot_enthalpy / cp0

    return np.ma.array(CT, mask=mask, copy=False)
