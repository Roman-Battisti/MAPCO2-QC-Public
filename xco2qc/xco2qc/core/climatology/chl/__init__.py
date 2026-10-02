# standard library imports
import importlib.resources as ir

# 3rd party library imports
import pandas as pd

# local imports
from . import data


# load the ?regular? (oa) and averaged (mn) O2 climatologies
with ir.as_file(ir.files(data).joinpath('Performance.of.NNI.for.GMIS.Chl.xlsx')) as path:
    chl = pd.read_excel(path)
