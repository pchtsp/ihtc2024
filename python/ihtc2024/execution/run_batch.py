from batch_functions import my_benchmark, rename_files

path_to_dir = "/home/pchtsp/Documents/projects/ihtc2024/results"
path_in = "/home/pchtsp/Documents/projects/ihtc2024/data/"

if __name__ == "__main__":
    # rename_files(path_to_dir)
    # my_benchmark(solver_name="cpsat", timeLimit=60 * 20, scenarios=["ihtc2024_test_dataset"], threads=8, report=dict(name='report'))
    my_benchmark(
        path_to_dir,
        path_in,
        solver_name="graph_tw",
        # solver_name="cpsat",
        timeLimit=60 * 20,
        # scenarios=["ihtc2024_competition_instances"],
        # scenarios=["ihtc2024_test_dataset"],
        # instances=['i01.json'],
        scenarios=["ihtc2024_test_dataset", "ihtc2024_competition_instances"],
        #   instances=["test10.json"],
        threads=8,
        report=dict(name="report"),
    )

    # my_benchmark(solver_name="graph_tw", timeLimit=60 * 20,
    # scenarios=["ihtc2024_test_dataset"], instances=["test01.json"], threads=8, report=dict(name='report'))

    # my_benchmark(solver_name="timefold_py", timeLimit=60 * 20, scenarios="competition")
    # my_benchmark(solver_name="cpsat", timeLimit=60 * 20, scenarios="competition")
    # my_benchmark(solver_name="graph", timeLimit=60 * 20, scenarios="competition")
    # my_benchmark(
    #     solver_name="graph",
    #     timeLimit=60 * 20,
    #     scenarios=["ihtc2024_test_dataset"],
    #     # scenarios=["ihtc2024_competition_instances"],
    #     # scenarios=["ihtc2024_test_dataset", "ihtc2024_competition_instances"],
    #     # instances=["i17.json"],
    #     #
    #     # instances=["i16.json"],
    #     seed=351956,
    #     maxSample=[7, 10, None],
    #     threads=8,
    #     report=dict(name='report')
    # )
