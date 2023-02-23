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

import chex
import jax.numpy as jnp
import pytest

from jumanji import specs
from jumanji.environments.routing.connector.specs import ObservationSpec
from jumanji.environments.routing.connector.types import Observation


class TestObservationSpec:
    @pytest.fixture
    def observation_spec(self) -> ObservationSpec:
        num_agents = 3
        grid_size = 6

        grid_spec = specs.BoundedArray(
            shape=(num_agents, grid_size, grid_size),
            dtype=int,
            name="observation",
            minimum=0,
            maximum=num_agents * 3 + 2,
        )

        action_mask_spec = specs.BoundedArray(
            shape=(num_agents, 5),
            dtype=bool,
            minimum=False,
            maximum=True,
            name="action_mask",
        )

        step_spec = specs.BoundedArray(
            shape=(), dtype=int, minimum=0, maximum=50, name="step"
        )
        return ObservationSpec(grid_spec, action_mask_spec, step_spec)

    @pytest.fixture
    def observation(self, observation_spec: ObservationSpec) -> Observation:
        return observation_spec.generate_value()

    def test_observation_spec__generate_value(
        self, observation_spec: ObservationSpec
    ) -> None:
        """Test generating a value which conforms to the observation spec."""
        assert isinstance(observation_spec.generate_value(), Observation)

    def test_observation_spec__validate_shape(
        self, observation_spec: ObservationSpec, observation: Observation
    ) -> None:
        """Test that a different shape of an observation element breaks the
        validation given the observation spec.
        """
        observation = observation_spec.validate(observation)
        modified_shape_observation = observation._replace(
            grid=observation.grid[None, ...]
        )
        with pytest.raises(ValueError):
            observation_spec.validate(modified_shape_observation)

    def test_observation_spec__validate_dtype(
        self, observation_spec: ObservationSpec, observation: Observation
    ) -> None:
        """Test that a different dtype of an observation element breaks the
        validation given the observation spec.
        """
        observation = observation_spec.validate(observation)
        modified_dtype_observation = observation._replace(
            grid=observation.grid.astype(jnp.float16)
        )
        with pytest.raises(ValueError):
            observation_spec.validate(modified_dtype_observation)

    def test_observation_spec__validate_object(
        self, observation_spec: ObservationSpec
    ) -> None:
        """Test that validating another object breaks the validation."""
        with pytest.raises(Exception):
            observation_spec.validate(None)  # type: ignore

    def test_observation_spec__replace(self, observation_spec: ObservationSpec) -> None:
        """Test the replace method of ObservationSpec. Check that replacing the value of an
        attribute changes the observation spec and that it only changes the specific attribute
        (the remaining attributes are unchanged)."""
        args = [
            (
                "grid_spec",
                observation_spec.grid_spec.replace(shape=(3, 4)),
            ),
            (
                "action_mask_spec",
                observation_spec.action_mask_spec.replace(shape=(6, 5)),
            ),
        ]

        for arg_name, new_value in args:
            old_spec = observation_spec
            new_spec = old_spec.replace(**{arg_name: new_value})
            assert new_spec != old_spec
            assert getattr(new_spec, arg_name) == new_value

            arg_names = {"grid_spec", "action_mask_spec"}.difference([arg_name])

            for attr_name in arg_names:
                chex.assert_equal(
                    getattr(new_spec, attr_name), getattr(old_spec, attr_name)
                )