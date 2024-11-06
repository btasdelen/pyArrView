from pyArrView import av
import numpy as np

a = np.random.random((10, 11, 12, 13, 14))

av(a, 'Test Array')

input('Press Enter to exit')