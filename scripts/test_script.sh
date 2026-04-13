#!/bin/bash

# Install using `pip install pepip` or `pip install -e .` from the project root.
# Test using different versions of numpy and pandas in different packages.

mkdir -p /tmp/pepip-test
cd /tmp/pepip-test
rm -rf temp*
mkdir temp1 temp2 temp3 temp4 temp5 temp6 temp7 temp8 temp9 temp10
cd temp1 && pepip install numpy pandas && cd ..
cd temp2 && pepip install numpy pandas && cd ..
cd temp3 && pepip install numpy pandas && cd ..
cd temp4 && pepip install numpy pandas && cd ..
cd temp5 && pepip install numpy pandas && cd ..
cd temp6 && pepip install numpy pandas && cd ..
cd temp7 && pepip install numpy pandas && cd ..
cd temp8 && pepip install numpy pandas && cd ..
cd temp9 && pepip install numpy pandas && cd ..
cd temp10 && pepip install numpy pandas && cd ..

# Now, check the storage used by each folder
ncdu
