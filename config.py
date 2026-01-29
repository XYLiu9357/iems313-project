from dataclasses import dataclass
import math


@dataclass
class CableType:
    name: str
    capacity: float
    cost_per_meter: float


@dataclass
class TransformerType:
    name: str
    rated_power: float
    cost: float


@dataclass
class Node:
    node_id: int
    x: float
    y: float


def get_dist(node1: Node, node2: Node) -> float:
    """
    Euclidean distance.
    """
    return math.sqrt((node1.x - node2.x) ** 2 + (node1.y - node2.y) ** 2)


@dataclass
class Edge:
    node1: Node
    node2: Node
    flow: float = 0.0
    cable_type: CableType | None = None
    num_cables: int = 0

    def get_cost(self) -> float:
        if self.cable_type is None:
            return 0.0
        return (
            self.num_cables
            * self.cable_type.cost_per_meter
            * get_dist(self.node1, self.node2)
        )
