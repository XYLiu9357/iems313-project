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
) -> tuple[float, dict[str, int] | None]:
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
        return mv_cost, None

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
        return mv_cost, None

    # DP path reconstruction
    transformer_usage: dict[str, int] = {}
    cur_power = max_power
    remaining_cost = transformer_cost
    while cur_power > 0:
        best_prev_power = -1
        best_transformer = None
        for tr in transformers:
            tr_power = int(tr.rated_power)
            prev_power = cur_power - tr_power
            if prev_power < 0:
                prev_power = 0

            # If dp[prev_power] + tr.cost equals dp[current_power],
            # this transformer could have been used
            if prev_power <= cur_power and dp[prev_power] + tr.cost == remaining_cost:
                best_prev_power = prev_power
                best_transformer = tr
                break

        if best_transformer is None:
            # If no exact match found, try to find the closest
            for tr in transformers:
                tr_power = int(tr.rated_power)
                prev_power = cur_power - tr_power
                if prev_power < 0:
                    prev_power = 0

                # Check if this step is feasible (cost-wise)
                if (
                    prev_power <= cur_power
                    and dp[prev_power] + tr.cost <= remaining_cost + 1e-9
                ):  # Allow floating point tolerance
                    best_prev_power = prev_power
                    best_transformer = tr
                    break

        if best_transformer is None:
            raise RuntimeError(
                "Unable to reconstruct path for best transformer combination"
            )

        # Record the transformer usage
        tr_name = best_transformer.name
        transformer_usage[tr_name] = transformer_usage.get(tr_name, 0) + 1

        # Move to previous state
        remaining_cost -= best_transformer.cost
        cur_power = best_prev_power

    # Return HV cost if it is better
    hv_total_cost = hv_cable_cost + transformer_cost
    if mv_cost <= hv_total_cost:
        return mv_cost, None
    else:
        return hv_total_cost, transformer_usage


def total_system_cost(
    ccp_x: float,
    ccp_y: float,
    turbines: list[Turbine],
    mv_cables: list[CableType],
    hv_cables: list[CableType] | None,
    transformers: list[TransformerType] | None,
    turbine_power: float,
) -> tuple[float, dict[str, int] | None]:
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
        return float("inf"), None

    ccp = CCP(0, ccp_x, ccp_y, None)

    # Stage 1: Collection
    _, collection_cost = design_collection_network(
        turbines, ccp, mv_cables, turbine_power
    )

    # Stage 2: Export
    onshore = Node(-1, 0.0, 0.0)
    total_power = turbine_power * len(turbines)
    export_cost, transformer_usage = compute_export_cost(
        ccp,
        onshore,
        total_power,
        mv_cables,
        hv_cables,
        transformers,
    )
    return collection_cost + export_cost, transformer_usage


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
        )[0]

    lo, hi = 0.0, 1.0
    while hi - lo > tol:
        m1 = lo + (hi - lo) / 3
        m2 = hi - (hi - lo) / 3

        if cost_at(m1) < cost_at(m2):
            hi = m2
        else:
            lo = m1

    t_opt = 0.5 * (lo + hi)

    # Build final CCP
    _, transformer_usage = total_system_cost(
        t_opt * cx,
        t_opt * cy,
        turbines,
        mv_cables,
        hv_cables,
        transformers,
        turbine_power,
    )
    return CCP(0, t_opt * cx, t_opt * cy, transformer_usage)
