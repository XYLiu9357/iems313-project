import pathlib
import logging
import pandas as pd
import matplotlib.pyplot as plt
from config import CableType, TransformerType, Edge
from network import Turbine, CCP, design_collection_network
from optimizer import optimize_ccp_on_ray

FIG_DPI = 200
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def generate_turbine_layout(num_rows: int, num_cols: int) -> list[Turbine]:
    turbines = []
    node_id = 1  # 0 is reserved for the CCP
    for row in range(num_rows):
        leftmost_x = 25000 if row % 2 == 0 else 25250
        y = 2000 + row * 750
        for col in range(num_cols):
            x = leftmost_x + 500 * col
            turbines.append(Turbine(node_id, x, y))
            node_id += 1
    return turbines


def generate_collection_procurement(edges: list[Edge]) -> pd.DataFrame:
    columns = [
        "node1_id",
        "node1_x",
        "node1_y",
        "node2_id",
        "node2_x",
        "node2_y",
        "cable_type",
        "num_cables",
        "max_power",
        "flow",
        "distance",
        "cost",
    ]
    result = {}

    for column in columns:
        result[column] = []

    for edge in edges:
        if edge.cable_type is None:
            raise ValueError("Found edge with undetermined cable type")

        result["node1_id"].append(edge.node1.node_id)
        result["node1_x"].append(edge.node1.x)
        result["node1_y"].append(edge.node1.y)

        result["node2_id"].append(edge.node2.node_id)
        result["node2_x"].append(edge.node2.x)
        result["node2_y"].append(edge.node2.y)

        result["cable_type"].append(edge.cable_type.name)
        result["num_cables"].append(edge.num_cables)
        result["max_power"].append(edge.num_cables * edge.cable_type.capacity)
        result["flow"].append(edge.flow)
        result["distance"].append(edge.get_dist())
        result["cost"].append(edge.get_cost())

    df = pd.DataFrame(result)
    df["node1_x"] = df["node1_x"].astype(float)
    df["node1_y"] = df["node1_y"].astype(float)
    df["node2_x"] = df["node2_x"].astype(float)
    df["node2_y"] = df["node2_y"].astype(float)
    df_sorted = df.sort_values(by=["node1_id", "node2_id"])
    return df_sorted


if __name__ == "__main__":
    cur_path = pathlib.Path(".")
    fig, axs = plt.subplots(2, 2, figsize=(10, 10))

    def solve(
        num_rows: int,
        num_cols: int,
        mv_cables: list[CableType],
        hv_cables: list[CableType] | None,
        transformers: list[TransformerType] | None,
        ax,
    ) -> tuple[CCP, list[Edge]]:
        logger.info(f"Solving problem for {num_rows} x {num_cols} turbines")
        logger.info(
            f"Available export cables: {mv_cables + hv_cables if hv_cables else mv_cables}"
        )
        turbine_layout = generate_turbine_layout(num_rows, num_cols)

        ccp = optimize_ccp_on_ray(
            turbine_layout,
            mv_cables,
            hv_cables,
            transformers,
        )

        mst_edges, total_cost = design_collection_network(
            turbine_layout, ccp, mv_cables
        )

        # Plot turbines
        ax.scatter(
            [t.x for t in turbine_layout],
            [t.y for t in turbine_layout],
            c="b",
            s=20,
            label="Turbines",
        )

        # Plot CCP
        ax.scatter(
            [ccp.x],
            [ccp.y],
            c="red",
            marker="*",
            s=80,
            label="Optimized CCP",
            zorder=5,
        )

        # Plot connections (edges)
        for edge in mst_edges:
            x_coords = [edge.node1.x, edge.node2.x]
            y_coords = [edge.node1.y, edge.node2.y]

            if edge.cable_type:
                color = "red"
                if edge.cable_type.name == "mv1":
                    color = "green"
                elif edge.cable_type.name == "mv2":
                    color = "orange"
                else:
                    raise ValueError(
                        f"Turbine-turbine and CCP-turbine connections can only be MV, found {edge.cable_type.name}"
                    )
                # Line width based on number of cables
                linewidth = 0.5 + edge.num_cables * 0.3
                ax.plot(
                    x_coords,
                    y_coords,
                    color=color,
                    linewidth=linewidth,
                    alpha=0.6,
                )
            else:
                raise ValueError("Found edge with undetermined cable type")

        # Report final solution
        logger.info(f"Number of mst_edges: {len(mst_edges)}")
        logger.info(f"total_cost = ${total_cost:,.2f}")

        hv_availability_str = "available" if hv_cables else "unavailable"
        ax.set_xlim(
            [
                min([turbine.x for turbine in turbine_layout]) - 500,
                max([turbine.x for turbine in turbine_layout]) + 500,
            ]
        )
        ax.set_ylim(
            [
                min([turbine.y for turbine in turbine_layout]) - 250,
                max([turbine.y for turbine in turbine_layout]) + 250,
            ]
        )
        ax.set_title(
            f"{num_rows} x {num_cols}, cost=${total_cost:,.0f}, HV {hv_availability_str}"
        )
        ax.set_aspect("equal")
        ax.grid(alpha=0.3)
        ax.legend()

        return ccp, mst_edges

    mv_cable_options = [CableType("mv1", 58.29, 1110), CableType("mv2", 90.87, 1515)]
    hv_cable_options = [CableType("hv1", 404.67, 1926), CableType("hv2", 490.41, 2475)]

    # SENSITIVITY ANALYSIS: CHANGE ME
    hv_transformers = [
        TransformerType("tr1", 180, 3.09e6),
        TransformerType("tr2", 360, 5.16e6),
    ]
    collection_dfs: list[tuple[str, pd.DataFrame]] = []

    # 1.1 HV available, 4 x 7
    ccp, edges = solve(
        4,
        7,
        mv_cable_options,
        hv_cable_options,
        hv_transformers,
        axs[0][0],
    )
    collection_procurement_df = generate_collection_procurement(edges)
    collection_dfs.append(("collection_4_7_hv", collection_procurement_df))
    logger.info(
        f"Results: CCP location = {(ccp.x, ccp.y)}, Transformer Usage = {ccp.transformer_usage}"
    )

    # 1.2 HV unavailable, 4 x 7
    ccp, edges = solve(
        4,
        7,
        mv_cable_options,
        None,
        None,
        axs[0][1],
    )
    collection_procurement_df = generate_collection_procurement(edges)
    collection_dfs.append(("collection_4_7_no_hv", collection_procurement_df))
    logger.info(
        f"Results: CCP location = {(ccp.x, ccp.y)}, Transformer Usage = {ccp.transformer_usage}"
    )

    # 2.1 HV available, 6 x 10
    ccp, edges = solve(
        6,
        10,
        mv_cable_options,
        hv_cable_options,
        hv_transformers,
        axs[1][0],
    )
    collection_procurement_df = generate_collection_procurement(edges)
    collection_dfs.append(("collection_6_10_hv", collection_procurement_df))
    logger.info(
        f"Results: CCP location = {(ccp.x, ccp.y)}, Transformer Usage = {ccp.transformer_usage}"
    )

    # 2.2 HV unavailable, 6 x 10
    ccp, edges = solve(
        6,
        10,
        mv_cable_options,
        None,
        None,
        axs[1][1],
    )
    collection_procurement_df = generate_collection_procurement(edges)
    collection_dfs.append(("collection_6_10_no_hv", collection_procurement_df))
    logger.info(
        f"Results: CCP location = {(ccp.x, ccp.y)}, Transformer Usage = {ccp.transformer_usage}"
    )

    # Write procurement to file
    excel_path = cur_path / "collection_procurement_results.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for sheet_name, df in collection_dfs:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    logger.info(f"Collection procurement data saved to {excel_path}")

    # Write figure to file
    fig_path = cur_path / "output_fig.png"
    fig.tight_layout()
    fig.savefig(fig_path, dpi=FIG_DPI)
    logger.info(f"Solution figure saved to {fig_path}")
