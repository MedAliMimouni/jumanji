from jumanji import specs
from jumanji.connect4 import Connect4
from jumanji.wrappers import MultiToSingleJaxEnv
from validation import JaxEnvironmentLoop, RandomAgent


def run_connect_4_random_jit() -> None:
    """Runs a random agent in Connect 4 using the jitted Jax Environment Loop. This serves as an
    example of how to use an agent on a JaxEnv environment using the JaxEnvironmentLoop."""
    wrapped_env = MultiToSingleJaxEnv(Connect4())
    action_spec: specs.DiscreteArray = wrapped_env.action_spec()  # type: ignore
    random_agent = RandomAgent(action_spec=action_spec)
    environment_loop = JaxEnvironmentLoop(
        environment=wrapped_env,
        agent=random_agent,
        n_steps=20,
        batch_size=10,
    )
    environment_loop.run(num_steps=1_000, ms=True)


if __name__ == "__main__":
    run_connect_4_random_jit()