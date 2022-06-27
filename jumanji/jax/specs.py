import abc
from typing import Any, Generic, Iterable, NamedTuple, Sequence, Tuple, TypeVar, Union

import chex
import dm_env.specs
import jax.numpy as jnp

from jumanji.jax.env import JaxEnv

T = TypeVar("T")


class Spec(abc.ABC, Generic[T]):
    """Adapted from dm_env.spec.Array. This is an augmentation of the Array spec to allow for nested
    specs. `self.name`, `self.generate_value` and `self.validate` methods are kept from the dm_env
    object."""

    def __init__(self, name: str = ""):
        """Initializes a new spec.

        Args:
            name: string containing a semantic name for the corresponding nested spec.
                Defaults to `''`.
        """
        self._name = name

    def __repr__(self) -> str:
        return f"Spec(name={repr(self.name)})"

    @property
    def name(self) -> str:
        """Returns the name of the nested spec."""
        return self._name

    @abc.abstractmethod
    def validate(self, value: T) -> T:
        """Checks if a (potentially nested) value (tree of observations, actions...) conforms to
        this spec.

        Args:
            value: a (potentially nested) structure of jax arrays.

        Returns:
            value.

        Raises:
            ValueError: if value doesn't conform to this spec.
        """

    @abc.abstractmethod
    def generate_value(self) -> T:
        """Generate a test value which conforms to this spec."""


class Array(Spec[chex.Array]):
    """Describes a jax array spec. This is adapted from dm_env.specs.Array to suit Jax environments.

    An `Array` spec allows an API to describe the arrays that it accepts or returns, before that
    array exists.
    """

    def __init__(self, shape: Iterable, dtype: Union[jnp.dtype, type], name: str = ""):
        """Initializes a new `Array` spec.

        Args:
            shape: an iterable specifying the array shape.
            dtype: jax numpy dtype or string specifying the array dtype.
            name: string containing a semantic name for the corresponding array. Defaults to `''`.
        """
        super().__init__(name)
        self._shape = tuple(int(dim) for dim in shape)
        self._dtype = jnp.dtype(dtype)

    def __repr__(self) -> str:
        return f"Array(shape={repr(self.shape)}, dtype={repr(self.dtype)}, name={repr(self.name)})"

    def __reduce__(self) -> Any:
        """To allow pickle to serialize the spec."""
        return Array, (self._shape, self._dtype, self._name)

    @property
    def shape(self) -> Tuple:
        """Returns a `tuple` specifying the array shape."""
        return self._shape

    @property
    def dtype(self) -> jnp.dtype:
        """Returns a jax numpy dtype specifying the array dtype."""
        return self._dtype

    def _fail_validation(self, message: str) -> None:
        if self.name:
            message += f" for spec {self.name}."
        else:
            message += "."
        raise ValueError(message)

    def validate(self, value: chex.Numeric) -> chex.Array:
        """Checks if value conforms to this spec.

        Args:
            value: a jax array or value convertible to one via `jnp.asarray`.

        Returns:
            value, converted if necessary to a jax array.

        Raises:
            ValueError: if value doesn't conform to this spec.
        """
        value = jnp.asarray(value)
        if value.shape != self.shape:
            self._fail_validation(
                f"Expected shape {self.shape} but found {value.shape}"
            )
        if value.dtype != self.dtype:
            self._fail_validation(
                f"Expected dtype {self.dtype} but found {value.dtype}"
            )
        return value

    def generate_value(self) -> chex.Array:
        """Generate a test value which conforms to this spec."""
        return jnp.zeros(shape=self.shape, dtype=self.dtype)


class BoundedArray(Array):
    """Bounded array spec that specifies minimum and maximum values for a jax environment. This is
    adapted from dm_env.specs.BoundedArray to suit Jax environments.

    Example usage:
    ```python
    # Specifying the same minimum and maximum for every element.
    spec = BoundedArray((3, 4), jnp.float_, minimum=0.0, maximum=1.0)

    # Specifying a different minimum and maximum for each element.
    spec = BoundedArray((2,), jnp.float_, minimum=[0.1, 0.2], maximum=[0.9, 0.9])

    # Specifying the same minimum and a different maximum for each element.
    spec = BoundedArray((3,), jnp.float_, minimum=-10.0, maximum=[4.0, 5.0, 3.0])
    ```

    Bounds are meant to be inclusive. This is especially important for integer types. The following
    spec will be satisfied by arrays with values in the set {0, 1, 2}:
    ```python
    spec = BoundedArray((3, 4), jnp.int_, minimum=0, maximum=2)
    ```

    Note that one or both bounds may be infinite. For example, the set of non-negative floats can be
    expressed as:
    ```python
    spec = BoundedArray((), jnp.float_, minimum=0.0, maximum=jnp.inf)
    ```
    In this case `jnp.inf` would be considered valid, since the upper bound is inclusive.
    """

    def __init__(
        self,
        shape: Iterable,
        dtype: Union[jnp.dtype, type],
        minimum: Union[chex.Numeric, Sequence],
        maximum: Union[chex.Numeric, Sequence],
        name: str = "",
    ):
        """
        Args:
            shape: an iterable specifying the array shape.
            dtype: jax numpy dtype or string specifying the array dtype.
            minimum: number or sequence specifying the minimum element bounds (inclusive).
                Must be broadcastable to `shape`.
            maximum: number or sequence specifying the maximum element bounds (inclusive).
                Must be broadcastable to `shape`.
            name: string containing a semantic name for the corresponding array. Defaults to `''`.

        Raises:
            ValueError: if `minimum` or `maximum` are not broadcastable to `shape`.
            ValueError: if any values in `minimum` are greater than their corresponding value
                in `maximum`.
            TypeError: if the shape is not an iterable or if the `dtype` is an invalid jax numpy
                dtype.
        """
        super().__init__(shape, dtype, name)
        minimum = jnp.asarray(minimum, dtype)
        maximum = jnp.asarray(maximum, dtype)
        try:
            bcast_minimum = jnp.broadcast_to(minimum, shape=shape)
        except ValueError as jnp_exception:
            raise ValueError(
                "`minimum` is incompatible with `shape`"
            ) from jnp_exception
        try:
            bcast_maximum = jnp.broadcast_to(maximum, shape=shape)
        except ValueError as jnp_exception:
            raise ValueError(
                "`maximum` is incompatible with `shape`"
            ) from jnp_exception

        if jnp.any(bcast_minimum > bcast_maximum):
            raise ValueError(
                f"All values in `minimum` must be less than or equal to their corresponding "
                f"value in `maximum`, got: \n\tminimum={repr(minimum)}\n\tmaximum={repr(maximum)}"
            )

        self._minimum = minimum
        self._maximum = maximum

    def __repr__(self) -> str:
        return (
            f"BoundedArray(shape={repr(self.shape)}, dtype={repr(self.dtype)}, "
            f"name={repr(self.name)}, minimum={repr(self.minimum)}, maximum={repr(self.maximum)})"
        )

    def __reduce__(self) -> Any:
        """To allow pickle to serialize the spec."""
        return BoundedArray, (
            self._shape,
            self._dtype,
            self._minimum,
            self._maximum,
            self._name,
        )

    @property
    def minimum(self) -> chex.Array:
        """Returns a Jax array specifying the minimum bounds (inclusive)."""
        return self._minimum

    @property
    def maximum(self) -> chex.Array:
        """Returns a Jax array specifying the maximum bounds (inclusive)."""
        return self._maximum

    def validate(self, value: chex.Numeric) -> chex.Array:
        value = super().validate(value)
        if (value < self.minimum).any() or (value > self.maximum).any():
            self._fail_validation(
                "Values were not all within bounds "
                f"{repr(self.minimum)} <= {repr(value)} <= {repr(self.maximum)}"
            )
        return value

    def generate_value(self) -> chex.Array:
        """Generate a jax array of the minima which conforms to this shape."""
        return jnp.ones(shape=self.shape, dtype=self.dtype) * self.minimum


class DiscreteArray(BoundedArray):
    """Represents a discrete, scalar, zero-based space. This is adapted from
    dme_env.specs.BoundedArray to suit Jax environments.

    This is a special case of the parent `BoundedArray` class. It represents a 0-dimensional jax
    array  containing a single integer value between 0 and num_values - 1 (inclusive), and exposes
    a scalar `num_values` property in addition to the standard `BoundedArray` interface.

    For an example use-case, this can be used to define the action space of a simple RL environment
    that accepts discrete actions.
    # TODO: make this multi-dimensional if possible.
    """

    def __init__(
        self, num_values: int, dtype: Union[jnp.dtype, type] = jnp.int_, name: str = ""
    ):
        """Initializes a new `DiscreteArray` spec.

        Args:
            num_values: integer specifying the number of possible values to represent.
            dtype: the dtype of the jax array. Must be an integral type.
            name: string containing a semantic name for the corresponding array. Defaults to `''`.

        Raises:
            ValueError: if `num_values` is not positive, if `dtype` is not integral.
        """
        if num_values <= 0 or not jnp.issubdtype(type(num_values), jnp.integer):
            raise ValueError(
                f"`num_values` must be a positive integer, got {num_values}."
            )

        if not jnp.issubdtype(dtype, jnp.integer):
            raise ValueError(f"`dtype` must be integral, got {dtype}.")

        num_values = int(num_values)
        maximum = num_values - 1
        super().__init__(shape=(), dtype=dtype, minimum=0, maximum=maximum, name=name)
        self._num_values = num_values

    def __repr__(self) -> str:
        return (
            f"DiscreteArray(shape={repr(self.shape)}, dtype={repr(self.dtype)}, "
            f"name={repr(self.name)}, minimum={repr(self.minimum)}, maximum={repr(self.maximum)}, "
            f"num_values={repr(self.num_values)})"
        )

    def __reduce__(self) -> Any:
        """To allow pickle to serialize the spec."""
        return DiscreteArray, (self._num_values, self._dtype, self._name)

    @property
    def num_values(self) -> int:
        """Returns the number of items."""
        return self._num_values


class EnvironmentSpec(NamedTuple):
    """Full specification of the domains used by a given environment."""

    observations: dm_env.specs.Array
    actions: dm_env.specs.Array
    rewards: dm_env.specs.Array
    discounts: dm_env.specs.Array


def make_environment_spec(jax_env: JaxEnv) -> EnvironmentSpec:
    """Returns an `EnvironmentSpec` describing values used by an environment."""
    return EnvironmentSpec(
        observations=jax_env.observation_spec(),
        actions=jax_env.action_spec(),
        rewards=jax_env.reward_spec(),
        discounts=jax_env.discount_spec(),
    )
