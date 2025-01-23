from functools import reduce

import numpy as np
import pandas as pd

from batch_functions import my_table

path_to_dir = "/home/pchtsp/Documents/projects/ihtc2024/results"
path_in = "/home/pchtsp/Documents/projects/ihtc2024/data/"

test_cases = dict(
    graph2="2025-01-22T0914-system76-pc",
    cpsat3="2025-01-21T1755-system76-pc",
    ref="reference",
    graphtw="2025-01-22T1246-system76-pc",
)
competition_cases = dict(
    # timefold_py="2024-11-08T2311-system76-pc",
    # cpsat="2024-11-09T1227-system76-pc",
    # cpsat2="2024-11-19T2108-system76-pc",
    cpsat3="2025-01-21T1756-system76-pc",
    graph2="2025-01-20T1004-system76-pc",
    graph3="2025-01-21T1145-system76-pc",
    # graph="2024-12-03T1206-system76-pc",
    graphtw="2025-01-22T1247-system76-pc",
)
if __name__ == "__main__":

    cases = competition_cases
    # cases = test_cases
    table_dict = {k: my_table(path_to_dir, v) for k, v in cases.items()}
    info2 = "errors"
    info2 = "time"
    info1 = "value"
    # info1 = "gap"
    # info2 = None

    for k, v in table_dict.items():
        v["method"] = k
        if info2 == "errors":
            my_errors = "[" + v["errors"].astype(str) + "]"
            my_errors[v["errors"] == 0] = ""
            v["value"] = v["objective"].astype(str) + my_errors
        else:
            # if we do not show errors, we do not show KPIs if there are errors
            v.loc[v["errors"] > 0, "objective"] = np.NAN
        if info2 == "time":
            v.loc[pd.isna(v["time"]), "time"] = -1
            my_time = "(" + v["time"].astype(int).astype(str) + ")"
            v["value"] = v["objective"].astype(str) + my_time
        if info2 is None:
            v["value"] = v["objective"]
        table_dict[k] = v[["name", "method", "value"]]

    df_all = pd.concat(table_dict.values(), axis=0)

    if info1 == "gap":
        df_all = pd.merge(
            df_all, df_all.groupby("name").value.min().rename("min"), on="name"
        )
        df_all["gap"] = (
            ((df_all["value"] - df_all["min"]) / df_all["min"]).round(2).astype(str)
        )
        df_all.loc[df_all["gap"] == "0.0", "gap"] = "*"
        aggfunc = lambda x: reduce(lambda a, b: a + " " + b, x)
    elif info2 is not None:
        # we're dealing with a string
        aggfunc = lambda x: " ".join(x)
    else:
        aggfunc = np.mean
    df_merged = pd.pivot_table(
        df_all, index="name", columns="method", values=info1, aggfunc=aggfunc
    )

    print(df_merged)
