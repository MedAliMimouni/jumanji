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
import jax
import jax.numpy as jnp
import pytest

from jumanji.environments.combinatorial.binpack.specs import ObservationSpec
from jumanji.environments.combinatorial.binpack.types import Observation


class TestObservationSpec:
    def test_observation_spec__generate_value(self, obs_spec: ObservationSpec) -> None:
        """Test generating a value which conforms to the observation spec."""
        assert isinstance(obs_spec.generate_value(), Observation)

    def test_observation_spec__validate(self, obs_spec: ObservationSpec) -> None:
        """Test the validation of an observation given the observation spec."""
        observation = obs_spec.validate(obs_spec.generate_value())
        # Check that a different shape breaks the validation
        with pytest.raises(ValueError):
            modified_ems_shape_observation = observation._replace(
                ems=jax.tree_map(lambda x: x[None, ...], observation.ems)
            )
            obs_spec.validate(modified_ems_shape_observation)
        # Check that a different dtype breaks the validation
        with pytest.raises(ValueError):
            modified_ems_dtype_observation = observation._replace(
                ems=jax.tree_map(lambda x: x.astype(jnp.float16), observation.ems)
            )
            obs_spec.validate(modified_ems_dtype_observation)
        # Check that validating another object breaks the validation
        with pytest.raises(Exception):
            obs_spec.validate(None)  # type: ignore

    def test_observation_spec__replace(self, obs_spec: ObservationSpec) -> None:
        """Call self.replace on each of the attributes of obs_spec with their shape being modified.
        Then, for each attribute spec, check that it was correctly replaced and that all other
        specs remain the same."""
        arg_list = [
            "ems_spec",
            "ems_mask_spec",
            "items_spec",
            "items_mask_spec",
            "items_placed_spec",
            "action_mask_spec",
        ]
        modified_specs = [
            obs_spec.ems_spec.replace(
                x1_spec=obs_spec.ems_spec.x1_spec.replace(shape=(2,))
            ),
            obs_spec.ems_mask_spec.replace(shape=(2,)),
            obs_spec.items_spec.replace(
                x_len_spec=obs_spec.items_spec.x_len_spec.replace(shape=(2,))
            ),
            obs_spec.items_mask_spec.replace(shape=(2,)),
            obs_spec.items_placed_spec.replace(shape=(2,)),
            obs_spec.action_mask_spec.replace(shape=(2,)),
        ]
        for arg, modified_spec in zip(arg_list, modified_specs):
            old_spec = obs_spec
            new_spec = old_spec.replace(**{arg: modified_spec})
            assert new_spec != old_spec
            chex.assert_equal(getattr(new_spec, arg), modified_spec)
            for attr_name in set(arg_list).difference([arg]):
                chex.assert_equal(
                    getattr(new_spec, attr_name), getattr(old_spec, attr_name)
                )
