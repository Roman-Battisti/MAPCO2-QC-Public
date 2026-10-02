import numpy as np
import pandas as pd
from xco2qc.climatology import ChlCache
index = pd.date_range(start='2021-11-15', end='2022-01-02', freq='3H')
latitude = np.linspace(0, 0, num=len(index))
longitude = np.linspace(-100, -102, num=len(index))
data = {'latitude': latitude, 'longitude': longitude}
df = pd.DataFrame(data, index=index)
o = ChlCache(df, verbosity='debug')
o.check_coverage()
o.run()
print(o.ts)

