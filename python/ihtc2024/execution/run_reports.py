from functools import reduce

import numpy as np
import pandas as pd

from batch_functions import my_table

path_to_dir = "/home/pchtsp/Documents/projects/ihtc2024/results"
path_in = "/home/pchtsp/Documents/projects/ihtc2024/data/"

test_cases = dict(
    cpsat="2025-01-23T1722-system76-pc",
    cpsat2step="2025-01-23T2133-system76-pc",
    graph="2025-01-24T0530-system76-pc",
    graphtw_2step="2025-01-27T1139-system76-pc",
    graphtw_both="2025-01-28T1205-system76-pc",
    ref="reference",
)
competition_cases = dict(
    cpsat2step="2025-01-23T2313-system76-pc",
    graph="2025-01-24T0557-system76-pc",
    graphTW_2step="2025-01-27T2102-system76-pc",
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
