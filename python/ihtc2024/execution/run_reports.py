from functools import reduce

import numpy as np
import pandas as pd

from run_batch import my_table

test_cases = dict(
    timefold_py="2024-11-08T1919-system76-pc",
    cpsat="2024-11-08T2130-system76-pc",
    graph="2024-11-15T1609-system76-pc",
    cpsat2="2024-11-18T1824-system76-pc",
    ref="reference",
)
competition_cases = dict(
    timefold_py="2024-11-08T2311-system76-pc",
    cpsat="2024-11-09T1227-system76-pc",
    cpsat3="2024-11-19T2108-system76-pc",
    graph="2024-11-20T2247-system76-pc",
)
if __name__ == "__main__":

    # cases = competition_cases
    cases = test_cases
    table_dict = {k: my_table(v) for k, v in cases.items()}
    info = "errors"
    info = "time"
    for k, v in table_dict.items():
        if info == "errors":
            my_errors = "[" + v["errors"].astype(str) + "]"
            my_errors[v["errors"] == 0] = ""
            v[k] = v["objective"].astype(str) + my_errors
        elif info == "time":
            my_time = "(" + v["time"].astype(int).astype(str) + ")"
            v[k] = v["objective"].astype(str) + my_time
            v.loc[v["errors"] > 0, k] = np.NAN
        else:
            v[k] = v["objective"]
        table_dict[k] = v[["name", k]]
    df_merged = reduce(
        lambda left, right: pd.merge(left, right, on=["name"], how="left"),
        table_dict.values(),
    )
    df_merged.sort_values("name", inplace=True)
    print(df_merged)
