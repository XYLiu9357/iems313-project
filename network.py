from config import Node, Edge, CableType, get_dist
import math


class Turbine(Node):
    def __init__(self, node_id: int, x: float, y: float) -> None:
        super().__init__(node_id, x, y)
        self.neighbors: list[Node] = []
        self.connected: list[Node] = []

    def add_neighbor(self, neighbor_node: Node) -> None:
        self.neighbors.append(neighbor_node)

    def add_neighbors(self, neighbors: list[Node]) -> None:
        self.neighbors.extend(neighbors)

    def get_neighbors(self) -> list[Node]:
        return self.neighbors.copy()  # shallow

    def get_connected(self) -> list[Node]:
        return self.connected.copy()  # shallow


class CCP(Node):
    def __init__(self, node_id: int, x: float, y: float) -> None:
        super().__init__(node_id, x, y)
        self.connected_turbines: list[Turbine] = []

    def connect_to_turbine(self, turbine: Turbine) -> None:
        self.connected_turbines.append(turbine)
        turbine.add_neighbor(self)

    def connect_to_turbines(self, turbines: list[Turbine]) -> None:
        for turbine in turbines:
            self.connect_to_turbine(turbine)

    def get_connected_turbines(self) -> list[Turbine]:
        return self.connected_turbines.copy()  # shallow


def build_rooted_mst(
    nodes: list[Node],
) -> tuple[list[Edge], dict[int, list[tuple[Node, Edge]]]]:
    """
    Build MST rooted at nodes[0] (which should be the CCP) using Prim's algorithm.
    Returns a list of MST edges and the rooted tree structure.
    """
    if len(nodes) <= 1:
        return [], {}

    root = nodes[0]
    in_mst: set[int] = {root.node_id}
    mst_edges: list[Edge] = []

    # Tree structure: parent_id -> [(child, edge), ...]
    tree: dict[int, list[tuple[Node, Edge]]] = {root.node_id: []}

    while len(in_mst) < len(nodes):
        min_edge = None
        min_distance = float("inf")
        parent_node = Node(-1, -1, -1)  # dummy node at the start
        for node in nodes:
            if node.node_id in in_mst:
                for other_node in nodes:
                    if other_node.node_id not in in_mst:
                        dist = get_dist(node, other_node)
                        if dist < min_distance:
                            min_distance = dist
                            min_edge = Edge(node, other_node)
                            parent_node = node

        if min_edge:
            mst_edges.append(min_edge)
            in_mst.add(min_edge.node2.node_id)

            # Add child to tree
            if parent_node.node_id not in tree:
                tree[parent_node.node_id] = []
            tree[parent_node.node_id].append((min_edge.node2, min_edge))
            # tree[min_edge.node2.node_id] = []

    return mst_edges, tree


def calculate_flows(
    tree: dict[int, list[tuple[Node, Edge]]], ccp: CCP, turbine_power: float = 12.0
) -> dict[tuple[int, int], float]:
    """
    Calculate power flow on each edge using DFS.
    Returns dict mapping (node1_id, node2_id) -> flow
    """
    flows: dict[tuple[int, int], float] = {}

    def dfs(node: Node) -> float:
        total_power = 0.0
        if isinstance(node, Turbine):
            total_power = turbine_power

        if node.node_id in tree:
            for child, edge in tree[node.node_id]:
                child_power = dfs(child)
                edge_key = (edge.node1.node_id, edge.node2.node_id)
                flows[edge_key] = child_power
                total_power += child_power

        return total_power

    dfs(ccp)
    return flows


def select_cable_bundle(
    required_flow: float, cable_options: list[CableType]
) -> tuple[CableType, int]:
    """
    Select the most cost-effective cable bundle for required flow.
    Returns (cable_type, number_of_cables).
    """
    best_option = ((CableType("DummyCable", 0.0, float("inf"))), 0)
    best_cost_per_meter = float("inf")

    for cable_type in cable_options:
        num_needed = math.ceil(required_flow / cable_type.capacity)
        cost_per_meter = num_needed * cable_type.cost_per_meter
        if cost_per_meter < best_cost_per_meter:
            best_cost_per_meter = cost_per_meter
            best_option = (cable_type, num_needed)

    return best_option


def update_node_connections(edges: list[Edge], ccp: CCP) -> None:
    """
    Update the Node objects to reflect determined connections.
    """
    connections: dict[int, set[int]] = {}
    for edge in edges:
        if edge.node1.node_id not in connections:
            connections[edge.node1.node_id] = set()
        if edge.node2.node_id not in connections:
            connections[edge.node2.node_id] = set()
        connections[edge.node1.node_id].add(edge.node2.node_id)
        connections[edge.node2.node_id].add(edge.node1.node_id)

    edge_map = {}
    for edge in edges:
        edge_map[(edge.node1.node_id, edge.node2.node_id)] = edge
        edge_map[(edge.node2.node_id, edge.node1.node_id)] = edge

    for edge in edges:
        # Update neighbors
        if isinstance(edge.node1, Turbine) and edge.node1.node_id not in [
            n.node_id for n in edge.node1.neighbors
        ]:
            edge.node1.add_neighbor(edge.node2)
        if isinstance(edge.node2, Turbine) and edge.node2.node_id not in [
            n.node_id for n in edge.node2.neighbors
        ]:
            edge.node2.add_neighbor(edge.node1)

        if isinstance(edge.node1, CCP) and isinstance(edge.node2, Turbine):
            if edge.node2 not in ccp.connected_turbines:
                ccp.connected_turbines.append(edge.node2)
        elif isinstance(edge.node2, CCP) and isinstance(edge.node1, Turbine):
            if edge.node1 not in ccp.connected_turbines:
                ccp.connected_turbines.append(edge.node1)


def design_collection_network(
    turbines: list[Turbine],
    ccp: CCP,
    cable_options: list[CableType],
    turbine_power: float = 12.0,
) -> tuple[list[Edge], float]:
    """
    Design collection network using capacity-aware MST algorithm.
    """
    # Step 1: Build MST with CCP as root
    all_nodes = [ccp] + turbines  # CCP must be first node
    mst_edges, tree = build_rooted_mst(all_nodes)  # type: ignore

    # Step 2: Calculate flow on each edge
    flows = calculate_flows(tree, ccp, turbine_power)

    # Step 3: Assign cable types based on flow
    for edge in mst_edges:
        edge_key = (edge.node1.node_id, edge.node2.node_id)
        if edge_key in flows:
            flow = flows[edge_key]
            cable_type, num_cables = select_cable_bundle(flow, cable_options)
            edge.flow = flow
            edge.cable_type = cable_type
            edge.num_cables = num_cables

    # Step 4: Update node connections
    update_node_connections(mst_edges, ccp)

    # Step 5: Calculate total cost
    total_cost = sum(edge.get_cost() for edge in mst_edges)

    return mst_edges, total_cost
