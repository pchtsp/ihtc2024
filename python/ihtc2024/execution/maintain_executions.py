from run_reports import competition_cases, test_cases
from run_batch import path_to_dir

import os

all = os.listdir(path_to_dir)

existing = set(competition_cases.values()) | set(test_cases.values())

print(set(all) - existing)
