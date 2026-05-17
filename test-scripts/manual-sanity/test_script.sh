#!/bin/bash

# Test by installing the same packages in multiple folders, 
# allowing to check the storage used by each folder.

mkdir -p /tmp/pepip-test
cd /tmp/pepip-test
rm -rf temp*

for i in {1..10}; do
	mkdir temp$i
	cd temp$i
	pepip install numpy pandas
	cd ..
done

# Now, check the storage used by each folder
ncdu
