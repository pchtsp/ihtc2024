# IHTC 2024 competition

## data

This directory includes the datasets provided by the organizers both for testing and evaluation.

## python

The `python` directory has the main code, including solving method.

Main components are:

* `python/ihtc2024/core/`: logic about pre-processing, post-processing, charts, validations and I/O.
* `python/ihtc2024/solver/cp_sat.py`: CP-SAT model to solve complete problem.
* `python/ihtc2024/graph/`: an attempt at creating a graph-based solution space for each patient.

To test the code, check `python/ihtc2024/tests/` or `python/ihtc2024/execution/` for examples of code.

## validator

The `validator` directory has validator code provided by the organizers. It needs to be compiled following their instructions:

Can be compiled by running:

````
g++ -o IHTP_Validator IHTP_Validator.cc
```

And can be used like this:

```
./IHTP_Validator.exe toy.json sol-toy.json
```

