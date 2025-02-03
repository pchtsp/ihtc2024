import pstats
from pstats import SortKey

p = pstats.Stats("profile.txt")
p.strip_dirs().sort_stats(-1).print_stats()
p.sort_stats(SortKey.CUMULATIVE).print_stats(30)
p.sort_stats(SortKey.TIME).print_stats(20)

"""
python -m cProfile -o profile.txt -m unittest ihtc2024.tests.test_graphs.TestInstance.test_profile_test10
python -m cProfile -o profile_1.txt -m unittest ihtc2024.tests.test_graphs.TestInstance.test_profile_test10_graphcreation

gprof2dot -f pstats profile.txt | dot -Tpng -o output.png
gprof2dot -f pstats profile.txt  -z node:470:get_nodes_ady_per_patient --node-thres=0.001 --edge-thres=0.001| dot -Tpng -o output.png
gprof2dot -f pstats profile_1.txt | dot -Tpng -o output.png
"""
