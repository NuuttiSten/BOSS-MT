#!/bin/bash

# load environment
module load openbabel/3.0.a1
module load amber/18
unset PYTHONPATH

### execute job (or any script)
export LC_ALL=en_US.utf8
cwd=$(pwd)
cd /projappl/project_2000382/nuutti/BOSS
pipenv run ./run_boss.sh $cwd in_2D

