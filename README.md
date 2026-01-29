# IEMS 313 Project

## Dependencies

In addition to `Python3`, the following third-party packages are required. Let me know if you need help setting this up.

```
pandas
matplotlib
openpyxl
```

I recommend [this video](https://www.youtube.com/watch?v=sDCtY9Z1bqE) if you need help setting up the environment.

## How to run the program

If you have GNU Make installed, just run
```
make
```
from the project's root directory. If not, run
```
python -m main
```
will run everything.

Once the run completes (which should take no more than 10 seconds):
- Procurement table is stored as an Excel file, which contains all the information necessary to reconstruct the topology: `collection_procurement_results.xlsx`.
- Topology is shown visually in `output_fig.png`. If a star appears in the legend but not on the screen, this is likely because the algorithm decided it is best to place the CCP at the onshore instead of close to the wind farm. This makes sense only if no HV cable is used - so either HV is unavailable as in parts 1.2 and 2.2, or in sensitivity analysis where the transformers are too expensive.
- Terminal output logs has a line that looks similar to the one shown below, which gives the optimal CCP location and corresponding transformer usage pattern. Note that this information is __NOT__ shown in the procurement table. When reporting, please copy this number from the terminal into the document.

```
Results: CCP location = (24741.333585934844, 3502.1979048583567), Transformer Usage = {'tr2': 2}
# CCP location = (x, y), Transformer Usage = {"transformer_type", num_transformer_used}
```

## How to do sensitivity analysis

I kept all the moving parts that require modification in the testing process inside `main.py`. This should be the only file you need to change. If not, then we are in some trouble and I will take a deeper dive on the code.


I left a comment in `main.py` that reads.
```
# SENSITIVITY ANALYSIS: CHANGE ME
```
Follow the instructions provided by the professor and scale the cost entry by `alpha`. Keep trying different values until at some point HV cable usage becomes 0 and the CCP is moved to (0, 0). The former is straightforward to understand: with more expensive transformers, HV cables become intractable to include in the network. The latter is a bit more subtle: if using pure MV cables to connect turbines and CCP, it doesn't make a different where we place the CCP, so long as the total export distance does not change. Due to the ternary search algorithm used in CCP location optimization, the CCP is always placed at the onshore (0, 0). TLDR: CCP far away from the farm is expected behavior.

## Pseudocode

Terminologies used in the pseudocode:
- [Minimum Spanning Tree (MST)](https://en.wikipedia.org/wiki/Minimum_spanning_tree)
- [Prim's Algorithm](https://en.wikipedia.org/wiki/Prim%27s_algorithm)
- [Ternary Search](https://en.wikipedia.org/wiki/Ternary_search)
- [Dynamic Programming (DP)](https://en.wikipedia.org/wiki/Dynamic_programming)
- [Knapsack](https://en.wikipedia.org/wiki/Knapsack_problem#)

I don't think we need to include these in the report, but it helps wrap one's head around the algorithm.

```
Input: onshore connection point (0, 0), list of turbines to connect, list of interconnection cables, list of export cables.
Output: a connection topology that satisfies all the requirements, CCP location and transformers used.


optimize_ccp_on_ray:
    # Performs ternary search on the line from (0, 0) to the centroid of turbines to find
    # CCP location that minimizes total cost (connection + export).
    centroid_x := mean(turbines_x), centroid_y := mean(turbines_y)

    lo, hi := 0.0, 1.0
    while hi - lo > tolerance:
        if get_total_system_cost(m1) < get_total_system_cost(m2):
            hi = m2
        else:
            lo = m1

    t_optimal := (lo + hi) / 2
    transformer_usage_optimal := get_total_system_cost(t_optimal)
    Return CCP at (t_optimal * centroid_x, t_optimal * centroid_y) with transformer_usage_optimal


get_total_system_cost: input real number t in [0.0, 1.0]
    # Compute connection cost, export cost, and transformer usage.
    Place dummy CCP at (t * centroid_x, t * centroid_y)

    # Enforce 250m rule
    if CCP is within 250m to any turbine:
        Return +inf and None

    connection_topology, connection_cost := design_connection_network(CCP, turbines)
    total_power_required := power_per_turbine * number_of_turbines

    % Note that transformer_usage defaults to None if HV is unavailable
    export_cost, transformer_usage := compute_export_cost(CCP, total_power_required)
    Return connection_cost + export_cost and transformer_usage


compute_export_cost: input CCP location and total power required
    for cable in mv_cables:
        bundled_cost_per_meter := ceil(total_power_required / cable.rated_power) * cable.cost_per_meter
        Accumulate minimum bundled cost per meter and corresponding (cable_type, num_cables)
    best_export_cost, transformer_usage = minimum_bundled_cost_per_meter * dist(CCP, onshore), None

    if HV cables are available:
        for cable in hv_cables:
            bundled_cost_per_meter := ceil(total_power_required / cable.rated_power) * cable.cost_per_meter
            Accumulate minimum bundled cost per meter and corresponding (cable_type, num_cables)

        Compute optimal transformer usage to achieve total_power_required using unbounded Knapsack DP
        hv_total_export_cost = minimum_bundled_cost_per_meter * dist(CCP, onshore) + transformer_cost_optimal
        Update best_export_cost and transformer_usage if HV offers lower total export cost

    Return best_export_cost and transformer_usage

    
design_connection_network: input CCP and turbines
    Run Prim's algorithm on fully connected graph containing turbines and CCP -> Obtain MST with distance as weight rooted at CCP
    Compute flows through each cable in the MST using depth-first search from CCP to all turbines
    for edge in MST:
        for cable in mv_cables:
            bundled_cost_per_meter := ceil(total_power_required / cable.rated_power) * cable.cost_per_meter
            Accumulate minimum bundled cost per meter and corresponding (cable_type, num_cables)
        Assign min-cost cable type and number of cables in the bundle to edge and update connections

    Return MST with cable information and connection cost
```
