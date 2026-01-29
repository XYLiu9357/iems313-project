from config import Node, CableType, TransformerType, get_dist
from network import CCP, Turbine, select_cable_bundle, design_collection_network
import math
import statistics


def compute_export_cost(
    ccp: CCP,
    onshore: Node,
    total_power: float,
    mv_cables: list[CableType],
    hv_cables: list[CableType] | None,
    transformers: list[TransformerType] | None,
) -> float:
    """
    Compute export system cost from CCP to onshore.
      - MV-only export
      - HV export with any number of transformers (unbounded)
    Returns the minimum feasible cost.
    """
    dist = get_dist(ccp, onshore)

    # MV-only export
    mv_cable, mv_num = select_cable_bundle(total_power, mv_cables)
    mv_cost = mv_num * mv_cable.cost_per_meter * dist

    # If HV not available, MV is the only option
    if hv_cables is None or transformers is None:
        return mv_cost

    # HV cable cost
    hv_cable, hv_num = select_cable_bundle(total_power, hv_cables)
    hv_cable_cost = hv_num * hv_cable.cost_per_meter * dist

    # Transformer sizing (using knapsack DP)
    max_power = int(math.ceil(total_power))
    INF = float("inf")

    # dp[p] = minimum transformer cost to reach >= p power
    dp = [INF] * (max_power + 1)
    dp[0] = 0.0
    for p in range(max_power + 1):
        if dp[p] == INF:
            continue
        for tr in transformers:
            next_p = min(max_power, p + int(tr.rated_power))
            dp[next_p] = min(dp[next_p], dp[p] + tr.cost)

    transformer_cost = dp[max_power]
    if transformer_cost == INF:
        return mv_cost

    hv_total_cost = hv_cable_cost + transformer_cost
    return min(mv_cost, hv_total_cost)


def total_system_cost(
    ccp_x: float,
    ccp_y: float,
    turbines: list[Turbine],
    mv_cables: list[CableType],
    hv_cables: list[CableType] | None,
    transformers: list[TransformerType] | None,
    turbine_power: float,
) -> float:
    """
    Stage 1 (collection) + Stage 2 (export) cost,
    with CCP feasibility constraint.
    """

    def is_ccp_feasible(
        ccp_x: float,
        ccp_y: float,
        turbines: list[Turbine],
        min_dist: float = 250.0,
    ) -> bool:
        for t in turbines:
            if math.hypot(ccp_x - t.x, ccp_y - t.y) < min_dist:
                return False
        return True

    if not is_ccp_feasible(ccp_x, ccp_y, turbines):
        return float("inf")

    ccp = CCP(0, ccp_x, ccp_y)

    # Stage 1: Collection
    _, collection_cost = design_collection_network(
        turbines, ccp, mv_cables, turbine_power
    )

    # Stage 2: Export
    onshore = Node(-1, 0.0, 0.0)
    total_power = turbine_power * len(turbines)

    export_cost = compute_export_cost(
        ccp,
        onshore,
        total_power,
        mv_cables,
        hv_cables,
        transformers,
    )

    return collection_cost + export_cost


def optimize_ccp_on_ray(
    turbines: list[Turbine],
    mv_cables: list[CableType],
    hv_cables: list[CableType] | None,
    transformers: list[TransformerType] | None,
    turbine_power: float = 12.0,
    tol: float = 1e-3,
) -> CCP:
    """
    Ternary search along the ray from (0,0) to centroid.
    """
    cx = statistics.mean(t.x for t in turbines)
    cy = statistics.mean(t.y for t in turbines)

    def cost_at(t: float) -> float:
        return total_system_cost(
            t * cx,
            t * cy,
            turbines,
            mv_cables,
            hv_cables,
            transformers,
            turbine_power,
        )

    lo, hi = 0.0, 1.0
    while hi - lo > tol:
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3

        if cost_at(m1) < cost_at(m2):
            hi = m2
        else:
            lo = m1

    t_opt = 0.5 * (lo + hi)
    return CCP(0, t_opt * cx, t_opt * cy)
