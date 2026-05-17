#!/bin/bash
# Test the usage of different package versions of numpy and pandas in different folders.

mkdir -p /tmp/pepip-test
cd /tmp/pepip-test
rm -rf temp*
mkdir temp1 temp2
cd temp1 && pepip install "numpy==2.4.4" "pandas==3.0.2" && cd ..
cd temp2 && pepip install "numpy==2.3.5" "pandas==2.3.0" && cd ..
./temp1/.venv/bin/python -c "import numpy; print(numpy.__version__); import pandas; print(pandas.__version__)"
./temp2/.venv/bin/python -c "import numpy; print(numpy.__version__); import pandas; print(pandas.__version__)"
