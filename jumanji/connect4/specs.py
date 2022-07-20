from typing import Any

from jumanji import specs
from jumanji.connect4.types import Observation


class ObservationSpec(specs.Spec[Observation]):
    def __init__(
        self,
        board_obs: specs.Array,
        action_mask: specs.Array,
    ):
        name = (
            "Observation(\n"
            f"\tboard: {board_obs.name},\n"
            f"\taction_mask: {action_mask.name},\n"
            ")"
        )
        super().__init__(name=name)
        self.board_obs = board_obs
        self.action_mask = action_mask

    def __repr__(self) -> str:
        return (
            "ObservationSpec(\n"
            f"\tboard_obs={repr(self.board_obs)},\n"
            f"\taction_mask={repr(self.action_mask)},\n"
            ")"
        )

    def generate_value(self) -> Observation:
        """Generate a value which conforms to this spec."""
        return Observation(
            board=self.board_obs.generate_value(),
            action_mask=self.action_mask.generate_value(),
        )

    def validate(self, value: Observation) -> Observation:
        """Checks if a Connect4 Observation conforms to the spec.

        Args:
            value: a Connect4 Observation

        Returns:
            value.

        Raises:
            ValueError: if value doesn't conform to this spec.
        """
        observation = Observation(
            board=self.board_obs.validate(value.board),
            action_mask=self.action_mask.validate(value.action_mask),
        )
        return observation

    def replace(self, **kwargs: Any) -> "ObservationSpec":
        """Returns a new copy of `ObservationSpec` with specified attributes replaced.

        Args:
            **kwargs: Optional attributes to replace.

        Returns:
            A new copy of `ObservationSpec`.
        """
        all_kwargs = {"board_obs": self.board_obs, "action_mask": self.action_mask}
        all_kwargs.update(kwargs)
        return ObservationSpec(**all_kwargs)