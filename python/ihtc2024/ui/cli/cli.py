import click
from pytups import SuperDict

from ihtc2024 import IntegratedHealtcareTimetable as app
import os

import functools

input_file_format = click.Path(
    exists=True, dir_okay=False, file_okay=True, readable=True
)


@click.group()
def cli():
    pass


def common_options(f):
    @click.option(
        "--instance", default=None, help="Input path (.json).", type=input_file_format
    )
    @click.option(
        "--solution",
        help="Solution path (.json).",
        default=None,
        type=input_file_format,
    )
    @click.option(
        "--excel", default=None, help="Dataset (.xlsx).", type=input_file_format
    )
    @click.option("--config", help="Optional configuration for solver.", default=None)
    @click.option("--test", help="Run test instance.", default=False, is_flag=True)
    @click.option("--report-path", help="Report path.", default="report.html")
    @functools.wraps(f)
    def wrapper_common_options(*args, **kwargs):
        return f(*args, **kwargs)

    return wrapper_common_options


@cli.command()
@common_options
@click.option("--output-path", "-o", help="Output path.", default="solution")
def solve_instance(instance, solution, excel, config, test, report_path, output_path):
    instance, solution = get_instance_solution(instance, solution, excel, test)
    if excel:
        extension = ".xlsx"
    else:
        extension = ".json"

    if config is None:
        config = {}

    filename, ext = os.path.splitext(output_path)
    if ext != extension:
        output_path = filename + extension

    my_app = app()

    sol, checks, instance_checks, log_txt, log_json = my_app.solve(
        data=instance, config=config, solution_data=solution
    )
    if not sol:
        return print("No solution found.")

    print("Solution:")

    Solution = my_app.solution
    Instance = my_app.instance
    instance = Instance.from_dict(instance)
    solution = Solution.from_dict(sol)
    my_solver = my_app.get_solver(my_app.get_default_solver_name())
    experiment = my_solver(instance, solution)
    if extension == ".json":
        Solution.from_dict(sol).to_json(output_path)
    elif extension == ".xlsx":
        experiment.to_excel(output_path)
    print(f"Solution saved in {output_path}")
    if config is not None:
        report_name = SuperDict(config).get_m("report", "name")
        if report_name is not None:
            curr_path = experiment.generate_report(report_name)
            os.rename(curr_path, report_path)
            print(f"Report saved in {report_path}")

    if checks:
        print("Checks:")
        print(checks)
    if instance_checks:
        print("Instance checks:")
        print(instance_checks)


@cli.command()
@common_options
def get_report(instance, solution, excel, config, test, report_path):
    """Generates a report for the problem."""
    instance, solution = get_instance_solution(instance, solution, excel, test)
    my_app = app()
    experiment = my_app.get_solver(my_app.get_default_solver_name()).from_dict(
        dict(instance=instance, solution=solution)
    )
    print("Starting to write the report")
    if config is None:
        report_name = "report"
    else:
        report_name = SuperDict(config).get_m("report", "name", default="report")
    curr_path = experiment.generate_report(report_name)
    if os.path.isdir(report_path):
        report_path = os.path.join(report_path, "report.html")
    os.rename(curr_path, report_path)
    print(f"Report saved in {report_path}")


def get_instance_solution(instance, solution, excel, test):
    """Application that optimizes the scheduling of nurses in a hospital."""
    if excel:
        if instance or solution or test:
            raise ValueError(
                "You can't provide an instance or solution or a test with an excel file."
            )
        instance = app.instance.from_excel(excel)
        try:
            solution = app.solution.from_excel(excel)
        except:
            # TODO: find out which exception is raised when there is no solution sheet.
            solution = None

    # We load the instance.
    if instance:
        instance = app.instance.from_json(instance).to_dict()
    # If a solution is provided, we load it.
    if solution:
        solution = app.solution.from_json(solution).to_dict()

    my_app = app()
    if test:
        if instance:
            raise ValueError("You can't provide a test flag and an instance.")
        test_cases = my_app.test_cases
        if len(test_cases) == 0:
            raise ValueError("No test cases found.")
        instance = test_cases[0]["instance"]
        solution = test_cases[0].get("solution")

    if instance is None:
        raise ValueError(
            "No instance was provided. Please provide an instance to solve."
        )
    return instance, solution


if __name__ == "__main__":
    cli()
