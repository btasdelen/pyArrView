## Installation

```bash
git clone git@github.com:btasdelen/pyArrView.git
cd pyArrView
pip install .
```

## Usage

```python
from pyArrView import av
import numpy as np

a = np.random.random((10, 11, 12, 13))
av(a, 'Random Array')
```
