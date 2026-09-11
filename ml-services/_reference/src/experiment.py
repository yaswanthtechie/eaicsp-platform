from dataclasses import dataclass


@dataclass
class ABExperiment:
    """
    Configuration for a two-variant A/B experiment.

    variant_a is the control/production version.
    variant_b is the challenger/staging version.
    """

    model_name: str
    variant_a: str
    variant_b: str
    traffic_percentage: int = 50

    def __post_init__(self) -> None:
        if not self.model_name.strip():
            raise ValueError("model_name cannot be empty.")

        if not self.variant_a.strip():
            raise ValueError("variant_a cannot be empty.")

        if not self.variant_b.strip():
            raise ValueError("variant_b cannot be empty.")

        if self.variant_a == self.variant_b:
            raise ValueError(
                "variant_a and variant_b must be different."
            )

        if not isinstance(self.traffic_percentage, int):
            raise TypeError(
                "traffic_percentage must be an integer."
            )

        if not 0 <= self.traffic_percentage <= 100:
            raise ValueError(
                "traffic_percentage must be between 0 and 100."
            )

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "variant_a": self.variant_a,
            "variant_b": self.variant_b,
            "traffic_percentage": self.traffic_percentage,
        }