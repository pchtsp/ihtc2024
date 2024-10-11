# installing graph-tool and adding it to venv:
# https://git.skewed.de/count0/graph-tool/wikis/installation-instructions
# https://jolo.xyz/blog/2018/12/07/installing-graph-tool-with-virtualenv

import graph_tool.all as gt

# at initialize time:
# 1 graph per patient, with all relevant nodes of solution space

# during solving:
# for each patient:
# 1. update weights
# 2. get the shortest path/ pattern for patient
# 3. apply path


def patient_to_graph(instance, patient):

    graph = gt.Graph()
    graph


if __name__ == "__main__":
    pass
