from run_reports import competition_cases, test_cases
from run_batch import path_to_dir, path_in
from ihtc2024.core import Solution

import os
import shutil


def clean_executions():
    DELETE = True

    all = os.listdir(path_to_dir)

    existing = set(competition_cases.values()) | set(test_cases.values())
    remove = set(all) - existing
    remove = [r for r in remove if r.startswith("202")]

    for _file in remove:
        full_path = os.path.join(path_to_dir, _file)
        if DELETE:
            print(_file)
            shutil.rmtree(full_path)
        else:
            print(_file)


def copy_reference_solutions(path_to_dir, path_to_data):
    dir_name = "ihtc2024_test_solutions"
    run_name = "reference"
    file_names = {f"test{n:02}.json": f"sol_test{n:02}.json" for n in range(1, 11)}
    my_path = os.path.join(path_to_dir, run_name)
    for root, dirs, files in os.walk(my_path):
        for file in files:
            if file != "output.json":
                continue
            full_path = os.path.join(root, file)
            new_path = os.path.join(root, "output_old.json")
            origin_path = os.path.join(
                path_to_data, dir_name, file_names[os.path.split(root)[1]]
            )
            try:
                my_solution = Solution.from_ihtc_json(origin_path)
                os.rename(full_path, new_path)
                my_solution.to_json(full_path)
            except:
                pass


if __name__ == "__main__":

    copy_reference_solutions(path_to_dir, path_in)
