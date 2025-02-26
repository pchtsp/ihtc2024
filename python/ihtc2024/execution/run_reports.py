from functools import reduce

import numpy as np
import pandas as pd
import sys
from batch_functions import my_table
from copy import deepcopy

path_to_dir = "/home/pchtsp/Documents/projects/ihtc2024/results"
path_in = "/home/pchtsp/Documents/projects/ihtc2024/data/"

test_cases = dict(
    g_0204="2025-02-04T1357-pchtsp-meerkat",
    gtw2_0214="2025-02-14T1010-pchtsp-meerkat",
    c2s_0215="2025-02-15T0303-pchtsp-meerkat",
    g_0215="2025-02-15T0051-pchtsp-meerkat",
    gcp_0220="2025-02-20T1346-pchtsp-meerkat",
    ref="reference",
)
competition_cases = dict(
    g_0204="2025-02-04T1421-pchtsp-meerkat",
    gtw2_0210="2025-02-10T1551-pchtsp-meerkat",
    gtw2_0214="2025-02-14T1426-pchtsp-meerkat",
    c2s_0215="2025-02-15T0514-pchtsp-meerkat",
    g_0215="2025-02-15T0108-pchtsp-meerkat",
    gtw_0224="2025-02-24T1523-pchtsp-meerkat",
)


def get_table(my_tables: dict[str, pd.DataFrame], main_info: str, secondary_info: str):
    my_tables = deepcopy(my_tables)
    for k, v in my_tables.items():
        v["method"] = k
        if secondary_info == "errors":
            my_errors = "[" + v["errors"].astype(str) + "]"
            my_errors[v["errors"] == 0] = ""
            v["value"] = v["objective"].astype(str) + my_errors
        else:
            # if we do not show errors, we do not show KPIs if there are errors
            v.loc[v["errors"] > 0, "objective"] = np.NAN
        if secondary_info == "time":
            v.loc[pd.isna(v["time"]), "time"] = -1
            my_time = "(" + v["time"].astype(int).astype(str) + ")"
            v["value"] = v["objective"].astype(str) + my_time
        if secondary_info is None:
            v["value"] = v["objective"]
        my_tables[k] = v[["name", "method", "value"]]

    df_all = pd.concat(my_tables.values(), axis=0)

    if main_info == "gap":
        df_all = pd.merge(
            df_all, df_all.groupby("name").value.min().rename("min"), on="name"
        )
        df_all["gap"] = (
            ((df_all["value"] - df_all["min"]) / df_all["min"]).round(2).astype(str)
        )
        df_all.loc[df_all["gap"] == "0.0", "gap"] = "*"
        aggfunc = lambda x: reduce(lambda a, b: a + " " + b, x)
    elif secondary_info is not None:
        # we're dealing with a string
        aggfunc = lambda x: " ".join(x)
    else:
        aggfunc = np.mean
    df_merged = pd.pivot_table(
        df_all, index="name", columns="method", values=main_info, aggfunc=aggfunc
    )
    return df_merged


if __name__ == "__main__":

    cases = competition_cases
    cases = test_cases

    if len(sys.argv) > 1:
        cases = competition_cases
        if sys.argv[1] == "t":
            cases = test_cases
    info2 = "time"
    info1 = "value"
    if len(sys.argv) > 2:
        cases = competition_cases
        if sys.argv[2] == "g":
            info1 = "gap"
            info2 = None

    # info2 = "errors"

    table_dict = {k: my_table(path_to_dir, v) for k, v in cases.items()}
    df_merged = get_table(table_dict, info1, info2)

    print(df_merged)
