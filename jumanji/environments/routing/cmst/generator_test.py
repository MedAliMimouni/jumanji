# Copyright 2022 InstaDeep Ltd. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Tuple

import jax
import jax.numpy as jnp
import networkx as nx
import numpy as np

from jumanji.environments.routing.cmst.constants import UTILITY_NODE
from jumanji.environments.routing.cmst.generator import SplitRandomGenerator


def check_generator(params: Tuple, data: Tuple) -> None:
    """Check it the graph data have been generated correctly."""

    (
        num_nodes,
        num_edges,
        max_degree,
        num_agents,
        num_nodes_per_agent,
        max_step,
    ) = params
    (
        node_types,
        edges,
        agents_pos,
        conn_nodes,
        conn_nodes_index,
        node_edges,
        nodes_to_connect,
    ) = data

    assert jnp.min(node_types) == UTILITY_NODE
    assert jnp.max(node_types) == num_agents - 1
    assert edges.shape == (num_agents, num_edges, 2)
    assert agents_pos.shape == (num_agents,)
    assert conn_nodes.shape == (num_agents, max_step)
    assert conn_nodes_index.shape == (num_agents, num_nodes)
    assert node_edges.shape == (num_nodes, num_nodes)
    assert nodes_to_connect.shape == (num_agents, num_nodes_per_agent)

    for i in range(num_edges):
        edge = edges[0, i]
        assert node_edges[edge[0], edge[1]] == edge[1]
        assert node_edges[edge[1], edge[0]] == edge[0]

    # Test that the graph is connected
    graph = nx.Graph()
    graph.add_nodes_from(list(range(num_nodes)))
    edges_list = list(np.asarray(edges[0]))
    graph.add_edges_from(edges_list)
    assert nx.is_connected(graph)


def test__generator() -> None:
    """Test if the graph generator work as expected."""

    problem_key = jax.random.PRNGKey(0)
    num_nodes = 100
    num_edges = 200
    max_degree = 10
    num_agents = 5
    num_nodes_per_agent = 5
    max_step = 50

    params = (
        num_nodes,
        num_edges,
        max_degree,
        num_agents,
        num_nodes_per_agent,
        max_step,
    )

    generator_fn = SplitRandomGenerator(*params)
    data = generator_fn(problem_key)
    check_generator(params, data)