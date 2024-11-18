from functools import reduce
import pandas as pd

from run_batch import my_table

test_cases = dict(
    timefold_py="2024-11-08T1919-system76-pc",
    cpsat="2024-11-08T2130-system76-pc",
    graph="2024-11-15T1609-system76-pc",
    ref="reference",
)
competition_cases = dict(
    timefold_py="2024-11-08T2311-system76-pc",
    cpsat="2024-11-09T1227-system76-pc",
    graph="2024-11-15T1610-system76-pc",
)
if __name__ == "__main__":

    table_dict = {k: my_table(v) for k, v in competition_cases.items()}
    for k, v in table_dict.items():
        my_errors = "[" + v["errors"].astype(str) + "]"
        my_errors[v["errors"] == 0] = ""
        v[k] = v["objective"].astype(str) + my_errors
        table_dict[k] = v[["name", k]]
    df_merged = reduce(
        lambda left, right: pd.merge(left, right, on=["name"], how="left"),
        table_dict.values(),
    )
    print(df_merged)
