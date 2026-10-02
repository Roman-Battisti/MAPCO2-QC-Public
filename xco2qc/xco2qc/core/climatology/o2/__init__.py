# standard library imports
import importlib.resources as ir

# 3rd party library imports
import pandas as pd

# local imports
from . import data


# load the ?regular? (oa) and averaged (mn) O2 climatologies
with ir.as_file(ir.files(data).joinpath('WOA18_Statistics_V2.xlsx')) as path:
    oa = pd.read_excel(path, sheet_name='oa', skiprows=1)

with ir.as_file(ir.files(data).joinpath('WOA18_Statistics_V2.xlsx')) as path:
    mn = pd.read_excel(path, sheet_name='mn', skiprows=1)
