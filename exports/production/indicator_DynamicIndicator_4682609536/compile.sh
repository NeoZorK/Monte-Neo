#!/bin/bash
echo 'Compiling Production C++ Indicator...'
g++ -O3 production_indicator.cpp -o production_indicator
if [ $? -eq 0 ]; then
  echo 'Successfully compiled to ./production_indicator'
else
  echo 'Compilation failed!'
  exit 1
fi
