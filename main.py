import pathlib
import logging
import matplotlib.pyplot as plt
from config import CableType, TransformerType
from network import Turbine, design_collection_network
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
    ) -> None:
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

    mv_cable_options = [CableType("mv1", 58.29, 1110), CableType("mv2", 90.87, 1515)]
    hv_cable_options = [CableType("hv1", 404.67, 1926), CableType("hv2", 490.41, 2475)]
    hv_transformers = [
        TransformerType("tr1", 180.0, 3.09e6),
        TransformerType("tr2", 360.0, 5.16e6),
    ]
    solve(
        4,
        7,
        mv_cable_options,
        hv_cable_options,
        hv_transformers,
        axs[0][0],
    )

    solve(
        4,
        7,
        mv_cable_options,
        None,
        None,
        axs[0][1],
    )

    solve(
        6,
        10,
        mv_cable_options,
        hv_cable_options,
        hv_transformers,
        axs[1][0],
    )

    solve(
        6,
        10,
        mv_cable_options,
        None,
        None,
        axs[1][1],
    )

    fig_path = cur_path / "output_fig.png"
    fig.tight_layout()
    fig.savefig(fig_path, dpi=FIG_DPI)
    logger.info(f"Solution figure saved to {fig_path}")
