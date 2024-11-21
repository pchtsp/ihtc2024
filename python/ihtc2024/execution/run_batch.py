from ihtc2024.core import Instance, ZipBatch, Batch, Solution
from ihtc2024.core import tools
from ihtc2024.solver import get_solver
import zipfile
import os
import shutil
from timeit import default_timer as timer
import logging as log
from typing import List
from datetime import datetime
import socket
from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_UNDEFINED,
)

path_to_dir = "/home/pchtsp/Documents/projects/ihtc2024/results"


def solve_zip(
    zip_name: str,
    path_out: str,
    path_in: str = "data/",
    solver_name: str = "default",
    test: bool = False,
    instances: List[str] = None,
    options: dict = None,
    zip_flag=True,
) -> None:
    if not os.path.exists(path_out):
        os.mkdir(path_out)
    batch_out_path = os.path.join(path_out, os.path.splitext(zip_name)[0])
    if options is None:
        options = {}
    backup_options = dict(options)
    # we recreate the whole batch output file
    # if os.path.exists(batch_out_path):
    #     shutil.rmtree(batch_out_path)
    if not os.path.exists(batch_out_path):
        os.mkdir(batch_out_path)

    path = os.path.join(path_in, zip_name)
    if zip_flag:
        zip_obj = zipfile.ZipFile(path)
        all_files = zip_obj.namelist()
    else:
        zip_obj = None
        all_files = os.listdir(path)
    if test:
        all_files = all_files[:3]
    if instances is not None:
        all_files = instances
    solver = get_solver(solver_name)
    if solver is None:
        raise ValueError(f"No solver found with name {solver_name}")
    # for each file:
    for filename in all_files:
        # filename = all_files[0]
        experiment_dir = os.path.join(batch_out_path, filename)
        if os.path.exists(experiment_dir):
            shutil.rmtree(experiment_dir)
        os.mkdir(experiment_dir)
        if zip_obj is not None:
            data = zip_obj.read(filename)
            inst = Instance.from_ihtc_json(path="", content=data.decode())
        else:
            full_name = os.path.join(path, filename)
            inst = Instance.from_ihtc_json(full_name)
        options = dict(backup_options)
        if options.get("logPath"):
            options["logPath"] = os.path.join(experiment_dir, options["logPath"])
        algo = solver(inst)
        start = timer()
        try:
            result = algo.solve(options)
        except Exception as e:
            result = dict(
                status=STATUS_UNDEFINED, status_sol=SOLUTION_STATUS_INFEASIBLE
            )
            with open(os.path.join(experiment_dir, "error.txt"), "w") as f:
                f.write(str(e))

        # export everything:
        _log = dict(
            time=timer() - start,
            solver=solver_name,
            status=result["status"],
            status_sol=result["status_sol"],
        )
        _log.update(options)
        tools.write_json(_log, os.path.join(experiment_dir, "options.json"))
        inst.to_json(os.path.join(experiment_dir, "input.json"))
        # we write the solution if it exists
        # even if it's not feasible
        if algo.solution is not None:
            algo.solution.to_json(os.path.join(experiment_dir, "output.json"))


def solve_scenarios_and_zip(
    scenarios: List[str],
    path_to_dir: str,
    solver_name: str,
    zip: bool = False,
    root_dir="data",
    **kwargs,
):
    zipfile_name = path_to_dir + ".zip"
    for scenario in scenarios:
        solve_zip(scenario, path_to_dir + "/", solver_name=solver_name, **kwargs)
    if not zip:
        return
    # root_dir = "data"
    base_dir = solver_name
    if os.path.exists(zipfile_name):
        os.remove(zipfile_name)
    shutil.make_archive(path_to_dir, "zip", root_dir=root_dir, base_dir=base_dir)


def get_table(path: str, is_zip_file=True):
    if is_zip_file:
        batch = ZipBatch(path)
    else:
        batch = Batch(path)
    objs = batch.get_objective_function()
    opts = batch.get_options()
    errors = batch.get_errors().vapply(lambda v: dict(errors=v))
    opts.update(errors)
    opts_df = batch.format_df(opts).drop(["instance"], axis=1)
    table = (
        batch.format_df(objs)
        .rename(columns={0: "objective"})
        .drop(["instance"], axis=1)
    )
    result = table.merge(opts_df, on=["scenario", "name"], how="left")
    return result


def my_benchmark(
    solver_name="cpsat",
    timeLimit=60 * 20,
    scenarios=None,
    my_range=None,
    instances=None,
    **options,
):
    path_to_dir = "/home/pchtsp/Documents/projects/ihtc2024/results"
    path_in = "/home/pchtsp/Documents/projects/ihtc2024/data/"
    # scenarios = ["ihtc2024_competition_instances"]
    if scenarios is None:
        scenarios = ["ihtc2024_test_dataset"]
        prefix = "test"
        if my_range is None:
            my_range = range(1, 6)
        instances = [f"{prefix}{str(i).rjust(2, '0')}.json" for i in my_range]
    elif scenarios == "competition":
        scenarios = ["ihtc2024_competition_instances"]
        prefix = "i"
        if my_range is None:
            my_range = range(1, 30)
        instances = [f"{prefix}{str(i).rjust(2, '0')}.json" for i in my_range]
    else:
        pass
    # zipfile_name = path_to_dir + ".zip"
    # we create a run with a timestamp
    timestamp = datetime.now().strftime("%Y-%m-%dT%H%M")
    pc = socket.gethostname()
    run_name = timestamp + "-" + pc
    path_to_dir = os.path.join(path_to_dir, run_name)
    if os.path.exists(path_to_dir):
        shutil.rmtree(path_to_dir)
    os.mkdir(path_to_dir)
    solve_scenarios_and_zip(
        scenarios,
        path_to_dir,
        solver_name,
        test=False,
        path_in=path_in,
        zip_flag=False,
        zip=False,
        options=dict(timeLimit=timeLimit, msg=True, logPath="log.txt", **options),
        instances=instances,
    )


def my_table(run_name):
    return get_table(path=os.path.join(path_to_dir, run_name), is_zip_file=False)


def rename_files():
    run_name = "reference"
    my_path = os.path.join(path_to_dir, run_name)
    for root, dirs, files in os.walk(my_path):
        for file in files:
            if file != "options.json":
                continue
            full_path = os.path.join(root, file)
            new_path = os.path.join(root, "output_old.json")
            my_solution = Solution.from_ihtc_json(full_path)
            os.rename(full_path, new_path)
            my_solution.to_json(full_path)


if __name__ == "__main__":
    # my_benchmark(solver_name="cpsat", timeLimit=60 * 20)
    # my_benchmark(solver_name="timefold_py", timeLimit=60 * 20, scenarios="competition")
    # my_benchmark(solver_name="cpsat", timeLimit=60 * 20, scenarios="competition")
    # my_benchmark(solver_name="graph", timeLimit=60 * 20, scenarios="competition")
    my_benchmark(
        solver_name="graph",
        timeLimit=60 * 20,
        # scenarios=["ihtc2024_test_dataset"],
        scenarios=["ihtc2024_competition_instances"],
        # scenarios=["ihtc2024_test_dataset", "ihtc2024_competition_instances"],
        # instances=[f"i{str(i).rjust(2, '0')}.json" for i in range(17, 31)],
        # instances=["i17.json"],
        seed=351956,
        maxSample=[7, 10, None],
        threads=8,
    )
