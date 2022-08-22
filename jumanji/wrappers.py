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

from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Optional,
    Tuple,
    TypeVar,
    Union,
)

import dm_env.specs
import gym
import jax
import jax.numpy as jnp
import numpy as np
from brax.envs import Env as BraxEnv
from brax.envs import State as BraxState
from chex import Array, PRNGKey
from jax import jit, random

from jumanji import specs
from jumanji.env import Environment
from jumanji.types import Action, TimeStep, restart, termination, transition

State = TypeVar("State")
Observation = TypeVar("Observation")

# Type alias that corresponds to ObsType in the Gym API
GymObservation = Union[np.ndarray, Dict[str, np.ndarray]]


class Wrapper(Environment[State], Generic[State]):
    """Wraps the environment to allow modular transformations.
    Source: https://github.com/google/brax/blob/main/brax/envs/env.py#L72
    """

    def __init__(self, env: Environment):
        super().__init__()
        self._env = env

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({repr(self._env)})"

    def __getattr__(self, name: str) -> Any:
        if name == "__setstate__":
            raise AttributeError(name)
        return getattr(self._env, name)

    @property
    def unwrapped(self) -> Environment:
        """Returns the wrapped env."""
        return self._env.unwrapped

    def reset(self, key: PRNGKey) -> Tuple[State, TimeStep]:
        """Resets the environment to an initial state.

        Args:
            key: random key used to reset the environment.

        Returns:
            state: State object corresponding to the new state of the environment,
            timestep: TimeStep object corresponding the first timestep returned by the environment,
        """
        return self._env.reset(key)  # type: ignore

    def step(self, state: State, action: Action) -> Tuple[State, TimeStep]:
        """Run one timestep of the environment's dynamics.

        Args:
            state: State object containing the dynamics of the environment.
            action: Array containing the action to take.

        Returns:
            state: State object corresponding to the next state of the environment,
            timestep: TimeStep object corresponding the timestep returned by the environment,
        """
        return self._env.step(state, action)  # type: ignore

    def observation_spec(self) -> specs.Spec:
        """Returns the observation spec."""
        return self._env.observation_spec()

    def action_spec(self) -> specs.Spec:
        """Returns the action spec."""
        return self._env.action_spec()

    def render(self, state: State) -> Any:
        """Compute render frames during initialisation of the environment.

        Args:
            state: State object containing the dynamics of the environment.
        """
        return self._env.render(state)

    def close(self) -> None:
        """Perform any necessary cleanup.

        Environments will automatically :meth:`close()` themselves when
        garbage collected or when the program exits.
        """
        return self._env.close()  # type: ignore

    def __enter__(self) -> "Wrapper":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class JumanjiToDMEnvWrapper(dm_env.Environment):
    """A wrapper that converts Environment to dm_env.Environment."""

    def __init__(self, env: Environment, key: Optional[PRNGKey] = None):
        """Create the wrapped environment.

        Args:
            env: `Environment`to wrap to a `dm_env.Environment`.
            key: optional key to initialize the `Environment` with.
        """
        self._env = env
        if key is None:
            self._key = random.PRNGKey(0)
        else:
            self._key = key
        self._state: Any
        self._jitted_reset: Callable[[PRNGKey], Tuple[State, TimeStep]] = jit(
            self._env.reset
        )
        self._jitted_step: Callable[[State, Action], Tuple[State, TimeStep]] = jit(
            self._env.step
        )

    def __repr__(self) -> str:
        return str(self._env.__repr__())

    def reset(self) -> dm_env.TimeStep:
        """Starts a new sequence and returns the first `TimeStep` of this sequence.

        Returns:
            A `TimeStep` namedtuple containing:
                - step_type: A `StepType` of `FIRST`.
                - reward: `None`, indicating the reward is undefined.
                - discount: `None`, indicating the discount is undefined.
                - observation: A NumPy array, or a nested dict, list or tuple of arrays.
                    Scalar values that can be cast to NumPy arrays (e.g. Python floats)
                    are also valid in place of a scalar array. Must conform to the
                    specification returned by `observation_spec()`.
        """
        reset_key, self._key = random.split(self._key)
        self._state, timestep = self._jitted_reset(reset_key)
        return dm_env.restart(observation=timestep.observation)

    def step(self, action: Action) -> dm_env.TimeStep:
        """Updates the environment according to the action and returns a `TimeStep`.

        If the environment returned a `TimeStep` with `StepType.LAST` at the
        previous step, this call to `step` will start a new sequence and `action`
        will be ignored.

        This method will also start a new sequence if called after the environment
        has been constructed and `reset` has not been called. Again, in this case
        `action` will be ignored.

        Args:
            action: A NumPy array, or a nested dict, list or tuple of arrays
                corresponding to `action_spec()`.

        Returns:
            A `TimeStep` namedtuple containing:
                - step_type: A `StepType` value.
                - reward: Reward at this timestep, or None if step_type is
                    `StepType.FIRST`. Must conform to the specification returned by
                    `reward_spec()`.
                - discount: A discount in the range [0, 1], or None if step_type is
                    `StepType.FIRST`. Must conform to the specification returned by
                    `discount_spec()`.
                - observation: A NumPy array, or a nested dict, list or tuple of arrays.
                    Scalar values that can be cast to NumPy arrays (e.g. Python floats)
                    are also valid in place of a scalar array. Must conform to the
                    specification returned by `observation_spec()`.
        """
        self._state, timestep = self._jitted_step(self._state, action)
        return dm_env.TimeStep(
            step_type=timestep.step_type,
            reward=timestep.reward,
            discount=timestep.discount,
            observation=timestep.observation,
        )

    def observation_spec(self) -> dm_env.specs.Array:
        """Returns the dm_env observation spec."""
        return specs.jumanji_specs_to_dm_env_specs(self._env.observation_spec())

    def action_spec(self) -> dm_env.specs.Array:
        """Returns the dm_env action spec."""
        return specs.jumanji_specs_to_dm_env_specs(self._env.action_spec())

    @property
    def unwrapped(self) -> Environment:
        return self._env


class MultiToSingleWrapper(Wrapper):
    """A wrapper that converts a multi-agent Environment to a single-agent Environment."""

    def __init__(
        self,
        env: Environment,
        reward_aggregator: Callable = jnp.sum,
        discount_aggregator: Callable = jnp.max,
    ):
        """Create the wrapped environment.

        Args:
            env: `Environment` to wrap to a `dm_env.Environment`.
            reward_aggregator: a function to aggregate all agents rewards into a single scalar
                value, e.g. sum.
            discount_aggregator: a function to aggregate all agents discounts into a single
                scalar value, e.g. max.
        """
        super().__init__(env)
        self._reward_aggregator = reward_aggregator
        self._discount_aggregator = discount_aggregator

    def _aggregate_timestep(self, timestep: TimeStep) -> TimeStep:
        """Apply the reward and discount aggregator to a multi-agent
            timestep object to create a new timestep object that consists
            of a scalar reward and discount value.

        Args:
            timestep: the multi agent timestep object.

        Return:
            a single agent compatible timestep object."""

        return TimeStep(
            step_type=timestep.step_type,
            observation=timestep.observation,
            reward=self._reward_aggregator(timestep.reward),
            discount=self._discount_aggregator(timestep.discount),
        )

    def reset(self, key: PRNGKey) -> Tuple[State, TimeStep]:
        """Resets the environment to an initial state.

        Args:
            key: random key used to reset the environment.

        Returns:
            state: State object corresponding to the new state of the environment,
            timestep: TimeStep object corresponding the first timestep returned by the environment,
        """
        state, timestep = self._env.reset(key)
        timestep = self._aggregate_timestep(timestep)
        return state, timestep

    def step(self, state: Any, action: Action) -> Tuple[State, TimeStep]:
        """Run one timestep of the environment's dynamics.

        The rewards are aggregated into a single value based on the given reward aggregator.
        The discount value is set to the largest discount of all the agents. This
        essentially means that if any single agent is alive, the discount value won't be zero.

        Args:
            state: State object containing the dynamics of the environment.
            action: Array containing the action to take.

        Returns:
            state: State object corresponding to the next state of the environment,
            timestep: TimeStep object corresponding the timestep returned by the environment,
        """
        state, timestep = self._env.step(state, action)
        timestep = self._aggregate_timestep(timestep)
        return state, timestep


class VmapWrapper(Wrapper):
    """Vectorized Jax env."""

    def reset(self, key: PRNGKey) -> Tuple[State, TimeStep]:
        """Resets the environment to an initial state.

        The first dimension of the key will dictate the number of concurrent environments.

        To obtain a key with the right first dimension, you may call `jax.random.split` on key
        with the parameter `num` representing the number of concurrent environments.

        Args:
            key: random keys used to reset the environments where the first dimension is the number
                of desired environments.

        Returns:
            state: State object corresponding to the new state of the environments,
            timestep: TimeStep object corresponding the first timesteps returned by the
                environments,
        """
        state, timestep = jax.vmap(self._env.reset)(key)
        return state, timestep

    def step(self, state: State, action: Action) -> Tuple[State, TimeStep]:
        """Run one timestep of the environment's dynamics.

        The first dimension of the state will dictate the number of concurrent environments.

        See `VmapWrapper.reset` for more details on how to get a state of concurrent
        environments.

        Args:
            state: State object containing the dynamics of the environments.
            action: Array containing the actions to take.

        Returns:
            state: State object corresponding to the next states of the environments,
            timestep: TimeStep object corresponding the timesteps returned by the environments,
        """
        state, timestep = jax.vmap(self._env.step)(state, action)
        return state, timestep

    def render(self, state: State) -> Any:
        """Render the first environment state of the given batch. The remaining elements of the batched state are ignored.

        Args:
            state: State object containing the current dynamics of the environment.
        """
        state_0 = jumanji.tree_utils.tree_slice(state, 0)
        return super().render(state_0)


class BraxToJumanjiWrapper(Environment):
    """A wrapper that converts a Brax environment to an Environment for standardisation,
    use with the `EnvironmentLoop` and to augment the API (add timesteps, metrics...).
    """

    def __init__(self, brax_env: BraxEnv):
        """Creates the Environment wrapper for Brax environments.

        Args:
            brax_env: Brax Env object that is not wrapped by a ResetWrapper
        """
        self._env = brax_env

    def reset(self, key: PRNGKey) -> Tuple[BraxState, TimeStep]:
        """Resets the environment to an initial state.

        Args:
            key: random key used to reset the environment.

        Returns:
            state: Brax State object corresponding to the new state of the environment,
            timestep: TimeStep object corresponding the first timestep returned by the environment,
        """
        state = self._env.reset(key)
        timestep = restart(observation=state.obs, extras=state.metrics)
        return state, timestep

    def step(self, state: BraxState, action: Action) -> Tuple[State, TimeStep]:
        """Run one timestep of the environment's dynamics.

        Args:
            state: Brax State object containing the dynamics of the environment.
            action: Array containing the action to take.

        Returns:
            state: Brax State object corresponding to the next state of the environment,
            timestep: TimeStep object corresponding the timestep returned by the environment,
        """
        state = self._env.step(state, action)
        timestep = jax.lax.cond(
            state.done,
            lambda _state: termination(
                reward=_state.reward, observation=_state.obs, extras=_state.metrics
            ),
            lambda _state: transition(
                reward=_state.reward, observation=_state.obs, extras=_state.metrics
            ),
            state,
        )
        return state, timestep

    def observation_spec(self) -> specs.Array:
        """Returns the observation spec.

        Returns:
            observation_spec: a `specs.Array` spec.
        """
        return specs.Array(
            shape=(self._env.observation_size,),
            dtype=float,
            name="observation",
        )

    def action_spec(self) -> specs.BoundedArray:
        """Returns the action spec.

        Returns:
            action_spec: a `specs.BoundedArray` spec.
        """
        return specs.BoundedArray(
            shape=(self._env.action_size,),
            dtype=float,
            minimum=-1.0,
            maximum=1.0,
            name="action",
        )

    @property
    def unwrapped(self) -> BraxEnv:
        return self._env


class AutoResetWrapper(Wrapper):
    """Automatically resets environments that are done. Once the terminal state is reached,
    the state, observation, and step_type are reset. The observation and step_type of the
    terminal TimeStep is reset to the reset observation and StepType.FIRST, respectively.
    The reward, discount, and extras retrieved from the transition to the terminal state.
    """

    def auto_reset(self, state: State, timestep: TimeStep) -> Tuple[State, TimeStep]:
        """Reset the state and overwrite `timestep.observation` with the reset observation
        if the episode has terminated.
        """
        state, reset_timestep = self._env.reset(state.key)  # type: ignore

        # Replace observation with reset observation.
        timestep = timestep.replace(  # type: ignore
            observation=reset_timestep.observation,
            step_type=reset_timestep.step_type,
        )

        return state, timestep

    def step(self, state: State, action: Action) -> Tuple[State, TimeStep]:
        """Step the environment, with automatic resetting if the episode terminates."""
        state, timestep = self._env.step(state, action)

        # Overwrite the state and timestep appropriately if the episode terminates.
        state, timestep = jax.lax.cond(
            timestep.last(),
            self.auto_reset,
            lambda *x: x,
            state,
            timestep,
        )

        return state, timestep


class JumanjiToGymWrapper(gym.Env):
    """A wrapper that converts Environment to one that follows the gym.Env API"""

    # Flag that prevents `gym.register` from misinterpreting the `_step` and
    # `_reset` as signs of a deprecated gym Env API.
    _gym_disable_underscore_compat: ClassVar[bool] = True

    def __init__(self, env: Environment, seed: int = 0, backend: Optional[str] = None):
        """Create the wrapped environment.

        Args:
            env: Environment to wrap to a gym.Env.
            seed: the seed that is used to initialize the environment's PRNG.
            backend: the XLA backend.
        """
        self._env = env
        self.metadata: Dict[str, str] = {}
        self.seed(seed)
        self.backend = backend
        self._state = None
        self.observation_space = specs.jumanji_specs_to_gym_spaces(
            self._env.observation_spec()
        )
        self.action_space = specs.jumanji_specs_to_gym_spaces(self._env.action_spec())

        def reset(key: PRNGKey) -> Tuple[State, Observation, Optional[Dict]]:
            """Reset function of a Jumanji environment to be jitted."""
            state, timestep = self._env.reset(key)
            return state, timestep.observation, timestep.extras

        self._reset = jax.jit(reset, backend=self.backend)

        def step(
            state: State, action: Action
        ) -> Tuple[State, Observation, Array, bool, Optional[Any]]:
            """Step function of a Jumanji environment to be jitted."""
            state, timestep = self._env.step(state, action)
            done = jnp.bool_(timestep.last())
            return state, timestep.observation, timestep.reward, done, timestep.extras

        self._step = jax.jit(step, backend=self.backend)

    def reset(
        self,
        *,
        seed: Optional[int] = None,
        return_info: bool = False,
        options: Optional[dict] = None,
    ) -> Union[GymObservation, Tuple[GymObservation, Optional[Any]]]:
        """Resets the environment to an initial state by starting a new sequence
        and returns the first `Observation` of this sequence.

        Returns:
            obs: an element of the environment's observation_space.
            info (optional): contains supplementary information such as metrics.
        """
        if seed is not None:
            self.seed(seed)
        key, self._key = random.split(self._key)  # type: Tuple[PRNGKey, PRNGKey]
        self._state, obs, extras = self._reset(key)

        # Convert the observation to a numpy array or a nested dict thereof
        obs = jumanji_to_gym_obs(obs)

        if return_info:
            info = jax.tree_map(np.asarray, extras)
            return obs, info
        else:
            return obs  # type: ignore

    def step(
        self, action: np.ndarray
    ) -> Tuple[GymObservation, float, bool, Optional[Any]]:
        """Updates the environment according to the action and returns an `Observation`.

        Args:
            action: A NumPy array representing the action provided by the agent.

        Returns:
            observation: an element of the environment's observation_space.
            reward: the amount of reward returned as a result of taking the action.
            terminated: whether a terminal state is reached.
            info: contains supplementary information such as metrics.
        """

        action = jnp.array(action)  # Convert input numpy array to JAX array
        self._state, obs, reward, done, extras = self._step(self._state, action)

        # Convert to get the correct signature
        obs = jumanji_to_gym_obs(obs)
        reward = float(reward)
        terminated = bool(done)
        info = jax.tree_map(np.asarray, extras)

        return obs, reward, terminated, info

    def seed(self, seed: int = 0) -> None:
        """Function which sets the seed for the environment's random number generator(s).

        Args:
            seed: the seed value for the random number generator(s).
        """
        self._key = jax.random.PRNGKey(seed)

    def render(self, mode: str = "human") -> None:
        """Renders the environment.

        Args:
            mode: currently not used since Jumanji does not currently support modes.
        """
        del mode
        self._env.render(self._state)

    def close(self) -> None:
        """Closes the environment, important for rendering where pygame is imported."""
        self._env.close()

    @property
    def unwrapped(self) -> Environment:
        return self._env


def jumanji_to_gym_obs(observation: Observation) -> GymObservation:
    """Convert a Jumanji observation into a gym observation.

    Args:
        observation: JAX pytree with (possibly nested) containers that
            either have the `__dict__` or `_asdict` methods implemented.

    Returns:
        Numpy array or nested dictionary of numpy arrays.
    """
    if isinstance(observation, jnp.ndarray):
        return np.asarray(observation)
    elif hasattr(observation, "__dict__"):
        # Applies to various containers including `chex.dataclass`
        return {
            key: jumanji_to_gym_obs(value) for key, value in vars(observation).items()
        }
    elif hasattr(observation, "_asdict"):
        # Applies to `NamedTuple` container.
        return {
            key: jumanji_to_gym_obs(value)
            for key, value in observation._asdict().items()  # type: ignore
        }
    else:
        raise NotImplementedError(
            "Conversion only implemented for JAX pytrees with (possibly nested) containers "
            "that either have the `__dict__` or `_asdict` methods implemented."
        )
