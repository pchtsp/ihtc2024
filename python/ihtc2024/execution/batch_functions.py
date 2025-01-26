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
import traceback
from cornflow_client.constants import (
    SOLUTION_STATUS_FEASIBLE,
    SOLUTION_STATUS_INFEASIBLE,
    STATUS_UNDEFINED,
)


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
        my_err_file = os.path.join(experiment_dir, "error.txt")
        start = timer()
        algo = solver(inst)
        err_write_mode = "a"
        try:
            result = algo.solve(options)
        except Exception as e:
            result = dict(
                status=STATUS_UNDEFINED, status_sol=SOLUTION_STATUS_INFEASIBLE
            )
            if not os.path.exists(my_err_file):
                err_write_mode = "w"

            with open(my_err_file, err_write_mode) as f:
                f.write(str(e))
                f.write(traceback.format_exc())

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
        # if report active, try to run it.
        report = options.get("report")
        if report and algo.solution is not None:
            try:
                dest_path = os.path.join(experiment_dir, "report.html")
                report_path = algo.generate_report(report["name"])
                shutil.move(report_path, dest_path)
            except Exception as e:
                if not os.path.exists(my_err_file):
                    err_write_mode = "w"

                with open(my_err_file, err_write_mode) as f:
                    f.write("Report failed")
                    f.write(str(e))
                    f.write(traceback.format_exc())


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
    path_to_dir: str,
    path_in: str,
    solver_name="cpsat",
    timeLimit=60 * 20,
    scenarios=None,
    my_range=None,
    instances=None,
    **options,
):
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


def my_table(path_to_dir, run_name):
    return get_table(path=os.path.join(path_to_dir, run_name), is_zip_file=False)
