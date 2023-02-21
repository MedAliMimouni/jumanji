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

from typing import Any, Tuple, Type

import chex
import jax
import jax.numpy as jnp
from chex import PRNGKey

from jumanji import specs
from jumanji.env import Environment
from jumanji.environments.routing.connector.constants import AGENT_INITIAL_VALUE
from jumanji.environments.routing.connector.generator import (
    InstanceGenerator,
    UniformRandomGenerator,
)
from jumanji.environments.routing.connector.reward import RewardFn, SparseRewardFn
from jumanji.environments.routing.connector.specs import ObservationSpec
from jumanji.environments.routing.connector.types import Agent, Observation, State
from jumanji.environments.routing.connector.utils import (
    is_valid_position,
    move,
    switch_perspective,
)
from jumanji.types import Action, TimeStep, restart


class Connector(Environment[State]):
    """The Connector environment is a multi-agent gridworld problem where each agent must connect a
    start to a target. However when moving through this gridworld the agent leaves an impassable
    trail behind it. Therefore agents must connect to their targets without overlapping the routes
    taken by any other agent.

    - observation - Observation
        - action mask: jax array (bool) of shape (num_agents, 5).
        - step: (int) the current episode step.
        - grid: jax array (int) of shape (num_agents, size, size):
            - each 2d array (size, size) along axis 0 is the agent's local observation.
            - agents have ids from 0 to (num_agents - 1)
            - with 2 agents you might have a grid like this:
              4 0 1
              5 0 1
              6 3 2
              which means agent 1 has moved from the top right of the grid down and is currently in
              the bottom right corner and is aiming to get to the middle bottom cell. Agent 2
              started in the top left and moved down once towards its target in the bottom left.

              This would just be agent 0's view, the numbers would be flipped for agent 1's view.
              So the full observation would be of shape (2, 3, 3).

    - action: jax array (int) of shape (num_agents,):
        - can take the values [0,1,2,3,4] which correspond to [No Op, Up, Right, Down, Left].
        - each value in the array corresponds to an agent's action.

    - reward_fn: function that takes old state, new state and action returns a reward for each
        agent.

    - episode termination: if an agent can't move, or the horizon is reached, or the agent connects
        to its target, it is considered done. Once all agents are done, the episode will terminate.
        - timestep discounts are of shape (num_agents,)

    - state: State:
        - key: jax PRNG key used to randomly spawn agents and targets.
        - grid: jax array (int) of shape (size, size) which corresponds to agent 0's observation.
        - step: (int) number of steps passed in the current episode.
    """

    def __init__(
        self,
        size: int = 8,
        num_agents: int = 3,
        reward_fn: Type[RewardFn] = SparseRewardFn,
        horizon: int = 50,
        generator: Type[InstanceGenerator] = UniformRandomGenerator,
        **reward_fn_kwargs: Any
    ) -> None:
        """Create the Connector Environment.

        Args:
            size: number of rows and columns in the grid.
            num_agents: number of agents in the grid (or equivalently, the number of targets).
            reward_fn: class of type RewardFn, whose __call__ is used as a reward function.
            horizon: the number of steps allowed before an episode terminates.
            generator: an InstanceGenerator that generates new grids.
            reward_fn_kwargs: arguments passed to the reward_fn's __init__ to configure it.
        """
        super().__init__()

        self._size = size
        self._num_agents = num_agents
        self._horizon = horizon

        self.agent_ids = jnp.arange(self._num_agents)

        self._reward_fn = reward_fn(**reward_fn_kwargs)
        self._generator = generator(size, num_agents)

    def reset(self, key: PRNGKey) -> Tuple[State, TimeStep]:
        """Resets the environment.

        Args:
            key: used to randomly generate the connector grid.

        Returns:
            state: `State` object corresponding to the new state of the environment.
            timestep: `TimeStep` object corresponding to the initial environment timestep.
        """
        generator_key, key = jax.random.split(key)
        state = self._generator(generator_key)

        action_mask = jax.vmap(self._get_action_mask, (0, None))(
            state.agents, state.grid
        )
        observation = Observation(
            grid=self._obs_from_grid(state.grid),
            action_mask=action_mask,
            step=state.step,
        )
        timestep = restart(observation=observation, shape=(self._num_agents,))

        return (
            State(key=key, grid=state.grid, step=jnp.int32(0), agents=state.agents),
            timestep,
        )

    def step(self, state: State, action: Action) -> Tuple[State, TimeStep]:  # type: ignore
        """Perform an environment step.

        Args:
            state: State object containing the dynamics of the environment.
            action: Array containing the actions to take for each agent.
                - 0 no op
                - 1 move up
                - 2 move right
                - 3 move down
                - 4 move left

        Returns:
            state: `State` object corresponding to the next state of the environment.
            timestep: `TimeStep` object corresponding the timestep returned by the environment.
        """
        pass

    def _obs_from_grid(self, grid: chex.Array) -> chex.Array:
        """Gets the observation vector for all agents."""
        return jax.vmap(switch_perspective, (None, 0, None))(
            grid, self.agent_ids, self._num_agents
        )

    def _get_action_mask(self, agent: Agent, grid: chex.Array) -> chex.Array:
        """Gets an agent's action mask."""
        # Don't check action 0 because no-op is always valid
        actions = jnp.arange(1, 5)

        def is_valid_action(action: int) -> chex.Array:
            agent_pos = move(agent.position, action)
            return is_valid_position(grid, agent, agent_pos)

        mask = jnp.ones(5, dtype=bool)
        mask = mask.at[actions].set(jax.vmap(is_valid_action)(actions))
        return mask

    def observation_spec(self) -> ObservationSpec:
        """Returns the observation spec for Connector environment.

        This observation contains the grid for each agent, the action mask for each agent and
        the current step.

        Returns:
            observation_spec: an `ObservationSpec` which contains the grid and the action mask spec.
        """
        grid_spec = specs.BoundedArray(
            shape=(self._num_agents, self._size, self._size),
            dtype=int,
            name="observation",
            minimum=0,
            maximum=self._num_agents * 3 + AGENT_INITIAL_VALUE,
        )
        action_mask_spec = specs.BoundedArray(
            shape=(self._num_agents, 5),
            dtype=bool,
            minimum=False,
            maximum=True,
            name="action_mask",
        )
        step_spec = specs.BoundedArray(
            shape=(), dtype=int, minimum=0, maximum=self._horizon, name="step"
        )
        return ObservationSpec(
            grid_spec=grid_spec, action_mask_spec=action_mask_spec, step_spec=step_spec
        )

    def action_spec(self) -> specs.MultiDiscreteArray:
        """Returns the action spec for the Connector environment.

        5 actions: [0,1,2,3,4] -> [No Op, Up, Right, Down, Left]. Since this is a multi-agent
        environment, the environment expects an array of actions of shape (num_agents,).

        Returns:
            observation_spec: MultiDiscreteArray of shape (num_agents,).
        """
        return specs.MultiDiscreteArray(
            num_values=jnp.array([5] * self._num_agents),
            name="action",
        )

    def reward_spec(self) -> specs.Array:
        """
        Returns:
            reward_spec: a `specs.Array` spec of shape (num_agents,). One for each agent.
        """
        return specs.Array(shape=(self._num_agents,), dtype=float, name="reward")

    def discount_spec(self) -> specs.BoundedArray:
        """
        Returns:
            discount_spec: a `specs.Array` spec of shape (num_agents,). One for each agent
        """
        return specs.BoundedArray(
            shape=(self._num_agents,),
            dtype=float,
            minimum=0.0,
            maximum=1.0,
            name="discount",
        )
