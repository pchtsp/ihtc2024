# IHTC 2024 competition

## data

This directory includes the datasets provided by the organizers both for testing and evaluation.

## python

The `python` directory has the main code, including solving method.

Main components are:

* `python/ihtc2024/README.md`: instructions on installing.
* `python/ihtc2024/core/`: logic about pre-processing, post-processing, charts, validations and I/O.
* `python/ihtc2024/solver/cp_sat.py`: CP-SAT model to solve complete problem or a time window neighborhood.
* `python/ihtc2024/graph/`: an attempt at creating a graph-based solution space for patients.
* `python/ihtc2024/report/`: quarto reports to visualize, check and explore a solution.

To test the code, check `python/ihtc2024/tests/` or `python/ihtc2024/execution/` for examples of code.

## validator

The `validator` directory has validator code provided by the organizers. It needs to be compiled following their instructions:

Can be compiled by running:

```
g++ -o IHTP_Validator IHTP_Validator.cc
```

And can be used like this:

```
./IHTP_Validator.exe toy.json sol-toy.json
```

## Basic information

* Name of team: Team 42
* Participants: Franco Peschiera (independent)
* Contact person: pchtsp@gmail.com


## Description of the search method and tools used

The method put in place is based on two large neighborhood searches. We describe each neighborhood first. Then we present the method to generate an initial solution.

### First neighborhood: shortest path in a graph-based representation

A graph is generated with all the potential assignments for any patient. This include, admission days, room assignment, operating theater as well as the nurse assigned per shift to the patient room. The graph is built in [Graph-tool](https://graph-tool.skewed.de/).

This graph can be easily filtered for each patient to limit the nodes and arcs to only the relevant to the patient (e.g., those where the admission date only fall during the patient's available start date range).

Once we modify the weights of the arcs in the graph, we can apply a shortest path algorithm to find the best assignment to a patient, given an existing solution.

The neighborhood is then applied in the following way:

1. We remove 1 or more patients from an existing solution.
2. We try to add them back one patient at a time by:
	a. Calculating all resources used.
	b. Modifying the arcs to take into account the marginal cost of making one assignment.
	c. Running a shortest path algorithm in the graph.
	d. Using the optimal path to potentially edit the solution (adding a patient, modifying the patient assignments or taking the patient out).


### Second neighborhood: time window optimization with CP model 2-step decomposition

A complete CP model is built to solve the IHTC problem. This model can be used to directly solve a complete instance of the problem to optimality. The model is built with Google OR-tools and solved with Google [CP-SAT solver](https://developers.google.com/optimization/cp/cp_solver).

It can also be used in a two step solving process. In the first step, all patient, operating theater and room variables are optimized together with all their relevant constraints. 
In the second step, the previous variables are fixed and only nurse variables (and constraints) are optimized to choose the best nurse assignment given a previously decided patient admission scheduling.

For the neighborhood, we apply this 2-step approach to a limited time window of the problem, i.e., to all assignments between a start and end date. This time window is of variable size. We also limit the possible combinations of patient-room assignment and patient-admission assignments via sampling. When solving the subproblem, all assignments that fall outside the time window are fixed. All assignments inside the time window are optimized.


### Initial solution using graph

The first neighborhood (graph-based) is used iteratively to greedily (and randomly) add one patient at a time to the solution. Once all patients are tried, the procedure stops. This procedure can be run with multi-start to then choose the best of all solutions.

