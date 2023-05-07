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

from abc import ABC, abstractmethod
from typing import Tuple

import jax
from chex import Array, PRNGKey
from jax import numpy as jnp

from jumanji.environments.routing.cmst.constants import EMPTY_NODE
from jumanji.environments.routing.cmst.utils import multi_random_walk


class Generator(ABC):
    """Base class for generators for the CMST environment."""

    def __init__(
        self,
        num_nodes: jnp.int32,
        num_edges: jnp.int32,
        max_degree: jnp.int32,
        num_agents: jnp.int32,
        num_nodes_per_agent: jnp.int32,
        max_step: jnp.int32,
    ) -> None:
        """Initialises a graph generator.

        Args:
            num_nodes: number of nodes in the graph.
            num_edges: number of edges in the graph.
            max_degree: maximum degree a node can have.
            num_agents: number of agents.
            num_nodes_per_agent: number of nodes to connect per agent.
        """
        self._num_nodes = num_nodes
        self._num_edges = num_edges
        self._max_degree = max_degree
        self._num_agents = num_agents
        self._num_nodes_per_agent = num_nodes_per_agent
        self._total_comps = num_nodes_per_agent * num_agents
        self._max_step = max_step

    @abstractmethod
    def __call__(self, key: PRNGKey) -> Tuple[Array, ...]:
        """Generates a random graph and different nodes to connect per agents.

        Returns:
            a tuple containing the node_types, edges, agent_positions, connected_nodes,
            connected_nodes_index, node_edges, nodes_to_connect.
        """


class SplitRandomGenerator(Generator):
    """Generates a random environments that is solvable by spliting the graph in multiple sub graphs.

    Returns a graph and with a desired number of edges and nodes to connect per agent.
    """

    def __init__(
        self,
        num_nodes: jnp.int32,
        num_edges: jnp.int32,
        max_degree: jnp.int32,
        num_agents: jnp.int32,
        num_nodes_per_agent: jnp.int32,
        max_step: jnp.int32,
    ) -> None:
        super().__init__(
            num_nodes, num_edges, max_degree, num_agents, num_nodes_per_agent, max_step
        )

    def __call__(self, key: PRNGKey) -> Tuple[Array, ...]:
        graph_key, key = jax.random.split(key)

        nodes = jnp.arange(self._num_nodes, dtype=jnp.int32)
        graph, nodes_per_sub_graph = multi_random_walk(
            nodes, self._num_edges, self._num_agents, self._max_degree, graph_key
        )

        node_edges = graph.node_edges
        edges = jnp.repeat(graph.edges[None, ...], self._num_agents, axis=0)

        state_nodes_to_connect = EMPTY_NODE * (
            jnp.ones((self._num_agents, self._num_nodes_per_agent), dtype=jnp.int32)
        )

        node_types = EMPTY_NODE * jnp.ones(self._num_nodes, dtype=jnp.int32)
        conn_nodes = EMPTY_NODE * jnp.ones(
            (self._num_agents, self._max_step), dtype=jnp.int32
        )
        conn_nodes_index = EMPTY_NODE * jnp.ones(
            (self._num_agents, self._num_nodes), dtype=jnp.int32
        )

        agents_pos = jnp.zeros((self._num_agents), dtype=jnp.int32)

        for agent in range(self._num_agents):
            select_key, key = jax.random.split(key)
            agent_components = jax.random.choice(
                select_key,
                nodes_per_sub_graph[agent],
                [self._num_nodes_per_agent],
                replace=False,
            )
            node_types = node_types.at[agent_components].set(agent)
            agents_pos = agents_pos.at[agent].set(agent_components[0])
            conn_nodes = conn_nodes.at[agent, 0].set(agent_components[0])
            conn_nodes_index = conn_nodes_index.at[agent, agent_components[0]].set(
                agent_components[0]
            )
            state_nodes_to_connect = state_nodes_to_connect.at[agent].set(
                agent_components
            )

        return (
            node_types,
            edges,
            agents_pos,
            conn_nodes,
            conn_nodes_index,
            node_edges,
            state_nodes_to_connect,
        )
