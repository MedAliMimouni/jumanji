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

import random
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import chex
import jax.numpy as jnp
import matplotlib.animation
import matplotlib.pyplot as plt
import numpy as np
from numpy.typing import NDArray

import jumanji.environments
from jumanji.environments.routing.cmst.types import State

grey = (100 / 255, 100 / 255, 100 / 255)
white = (255 / 255, 255 / 255, 255 / 255)
yellow = (200 / 255, 200 / 255, 0 / 255)
red = (200 / 255, 0 / 255, 0 / 255)
black = (0 / 255, 0 / 255, 0 / 255)
blue = (50 / 255, 50 / 255, 160 / 255)


class Renderer:
    """Viewer class for the Cooperative Minimum Spanning Tree environment."""

    def __init__(
        self,
        num_agents: int,
        nodes_to_connect: chex.Array,
        num_nodes: int,
        edges: chex.Array,
        name: str = "cmst",
    ) -> None:
        """Create a ConnectorRenderer instance for rendering the Connector environment.

        Args:
            num_agents: Number of agents in the environment.
            nodes_to_connect: The nodes to connect by each agent.
            num_nodes: The total number of nodes.
            edges: The edges of the graph.
        """

        self.num_agents = num_agents

        self.num_nodes = num_nodes
        self.nodes_to_connect = nodes_to_connect
        self._name = name

        self.node_scale = 5 + int(np.sqrt(self.num_nodes))
        self.node_radius = 0.05 * 5 / self.node_scale

        adj_matrix = jnp.zeros((num_nodes, num_nodes), dtype=int)
        num_edges = edges.shape[1]
        for i in range(num_edges):
            adj_matrix = adj_matrix.at[edges[0, i, 0], edges[0, i, 1]].set(1)
            adj_matrix = adj_matrix.at[edges[0, i, 1], edges[0, i, 0]].set(1)

        self.positions = self._spring_layout(adj_matrix)

        # Pick display method. Only one mode avaliable
        self._display: Callable[[plt.Figure], Optional[NDArray]]
        self._display = self._display_human

        np.random.seed(0)
        random.seed(0)

        self.palette: List[Tuple[float, float, float]] = []

        for _ in range(num_agents):
            colour = (
                np.random.randint(0, 192) / 255,
                np.random.randint(0, 192) / 255,
                np.random.randint(0, 192) / 255,
            )
            self.palette.append(colour)

        self._animation: Optional[matplotlib.animation.Animation] = None

    def render(self, state: State, save_path: Optional[str] = None) -> chex.Array:
        """Render the state of the environment.

        Args:
            state: the current state of the environment to render.
            save_path: optional name to save frame as.

        Return:
            pixel RGB array
        """

        self._clear_display()
        fig, ax = self._get_fig_ax()
        fig.subplots_adjust(left=0.1, right=0.9, bottom=0.1, top=0.9)
        ax.clear()
        self._draw_graph(state, ax)
        if save_path:
            fig.savefig(save_path, bbox_inches="tight", pad_inches=0.2)

        return self._display(fig)

    def _draw_graph(self, state: State, ax: plt.Axes) -> None:
        """Draw the different nodes and edges in the graph

        Args:
            state: current state of the environment.
            ax: figure axes on which to plot.
        """

        edges = self.build_edges(state.edges, state.connected_nodes)
        # draw edges
        for e in edges.values():
            (n1, n2), color = e
            n1, n2 = int(n1), int(n2)
            x_values = [self.positions[n1][0], self.positions[n2][0]]
            y_values = [self.positions[n1][1], self.positions[n2][1]]
            ax.plot(x_values, y_values, c=color, linewidth=2)

        # draw nodes
        for node in range(self.num_nodes):
            pos = np.where(self.nodes_to_connect == node)[0]
            if len(pos) == 1:
                fcolor = self.palette[pos[0]]
            else:
                fcolor = black

            if node in state.position:
                lcolor = yellow
            else:
                lcolor = grey

            self.circle_fill(
                self.positions[node],
                lcolor,
                fcolor,
                self.node_radius,
                0.2 * self.node_radius,
                ax,
            )

            ax.text(
                self.positions[node][0],
                self.positions[node][1],
                node,
                color="white",
                ha="center",
                va="center",
                weight="bold",
            )

    def build_edges(
        self, edges_arr: chex.Array, connected_nodes: chex.Array
    ) -> Dict[Tuple[int, ...], List[Tuple[float, ...]]]:

        # normalize id for either order
        def edge_id(n1: int, n2: int) -> Tuple[int, ...]:
            return tuple(sorted((n1, n2)))

        # might be slow but for now we will always build all the edges
        edges: Dict[Tuple[int, ...], List[Tuple[float, ...]]] = {}

        # convert to numpy
        edges_arr = np.asarray(edges_arr)
        connected_nodes = np.asarray(connected_nodes)

        for edge in edges_arr:
            n1, n2 = edge
            eid = edge_id(n1, n2)
            if eid not in edges:
                edges[eid] = [(n1, n2), grey]

        for agent in range(self.num_agents):
            conn_group = connected_nodes[agent]
            len_conn = np.where(conn_group != -1)[0][
                -1
            ]  # get last index where node is not -1
            for i in range(len_conn):
                eid = edge_id(conn_group[i], conn_group[i + 1])
                edges[eid] = [(conn_group[i], conn_group[i + 1]), self.palette[agent]]

        return edges

    def circle_fill(
        self,
        xy: chex.Array,
        line_color: Tuple[float, float, float],
        fill_color: Tuple[float, float, float],
        radius: float,
        thickness: float,
        ax: plt.Axes,
    ) -> None:
        ax.add_artist(plt.Circle(xy, radius, color=line_color))
        ax.add_artist(plt.Circle(xy, radius - thickness, color=fill_color))

    def animate(
        self,
        states: Sequence[State],
        interval: int = 2000,
        save_path: Optional[str] = None,
    ) -> matplotlib.animation.FuncAnimation:
        """Create an animation from a sequence of Connector grids.
        Args:
            states: sequence of states to consecutive timesteps.
            interval: delay between frames in milliseconds, default to 2000.
            save_path: the path where the animation file should be saved. If it is None, the plot
                will not be saved.
        Returns:
            Animation that can be saved as a GIF, MP4, or rendered with HTML.
        """
        fig, ax = plt.subplots(
            num=f"{self._name}Animation", figsize=(self.node_scale, self.node_scale)
        )
        plt.close(fig)

        def make_frame(grid_index: int) -> None:
            ax.clear()
            state = states[grid_index]
            self._draw_graph(state, ax)

        # Create the animation object.
        self._animation = matplotlib.animation.FuncAnimation(
            fig,
            make_frame,
            frames=len(states),
            interval=interval,
        )

        # Save the animation as a gif.
        if save_path:
            self._animation.save(save_path)

        return self._animation

    def close(self) -> None:
        plt.close(self._name)

    def _get_fig_ax(self) -> Tuple[plt.Figure, plt.Axes]:
        recreate = not plt.fignum_exists(self._name)
        fig = plt.figure(self._name, (self.node_scale, self.node_scale))
        # plt.style.use("dark_background")
        if recreate:
            if not plt.isinteractive():
                fig.show()
            ax = fig.add_subplot()
        else:
            ax = fig.get_axes()[0]
        return fig, ax

    def _display_human(self, fig: plt.Figure) -> None:
        if plt.isinteractive():
            # Required to update render when using Jupyter Notebook.
            fig.canvas.draw()
            if jumanji.environments.is_notebook():
                plt.show(self._name)
        else:
            # Required to update render when not using Jupyter Notebook.
            fig.canvas.draw_idle()
            fig.canvas.flush_events()

    def _clear_display(self) -> None:
        if jumanji.environments.is_notebook():
            import IPython.display

            IPython.display.clear_output(True)

    def _compute_repulsive_forces(
        self, repulsive_forces: np.ndarray, pos: np.ndarray, k: float
    ) -> np.ndarray:
        for i in range(self.num_nodes):
            for j in range(i + 1, self.num_nodes):
                delta = pos[i] - pos[j]
                distance = np.linalg.norm(delta)
                direction = delta / (distance + 1e-6)
                force = k * k / (distance + 1e-6)
                repulsive_forces[i] += direction * force
                repulsive_forces[j] -= direction * force

        return repulsive_forces

    def _compute_attractive_forces(
        self,
        graph: chex.Array,
        attractive_forces: np.ndarray,
        pos: np.ndarray,
        k: float,
    ) -> np.ndarray:
        for i in range(self.num_nodes):
            for j in range(self.num_nodes):
                if graph[i, j]:
                    delta = pos[i] - pos[j]
                    distance = np.linalg.norm(delta)
                    direction = delta / (distance + 1e-6)
                    force = distance * distance / k
                    attractive_forces[i] -= direction * force
                    attractive_forces[j] += direction * force

        return attractive_forces

    def _spring_layout(
        self, graph: chex.Array, seed: int = 42
    ) -> List[Tuple[float, float]]:
        """
        Compute a 2D spring layout for the given graph using
        the Fruchterman-Reingold force-directed algorithm.

        The algorithm computes a layout by simulating the graph as a physical system,
        where nodes are repelling each other and edges are attracting connected nodes.
        The method minimizes the energy of the system over several iterations.

        Args:
            graph: A Graph object representing the adjacency matrix of the graph.
            seed: An integer used to seed the random number generator for reproducibility.

        Returns:
            A list of tuples representing the 2D positions of nodes in the graph.
        """
        rng = np.random.default_rng(seed)
        pos = rng.random((self.num_nodes, 2)) * 2 - 1

        iterations = 100
        k = np.sqrt(1 / self.num_nodes)
        temperature = 2.0  # Added a temperature variable

        for _ in range(iterations):
            repulsive_forces = self._compute_repulsive_forces(
                np.zeros((self.num_nodes, 2)), pos, k
            )
            attractive_forces = self._compute_attractive_forces(
                graph, np.zeros((self.num_nodes, 2)), pos, k
            )

            pos += (repulsive_forces + attractive_forces) * temperature
            # Reduce the temperature (cooling factor) to refine the layout.
            temperature *= 0.9

            pos = np.clip(pos, -1, 1)  # Keep positions within the [-1, 1] range

        return [(float(p[0]), float(p[1])) for p in pos]
