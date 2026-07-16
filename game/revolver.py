from __future__ import annotations
import secrets
from dataclasses import dataclass, field


@dataclass
class Revolver:
    chamber_count: int = 6
    _loaded_index: int | None = field(default=None, repr=False)
    _position: int = field(default=0, repr=False)
    _fired: bool = field(default=False, repr=False)
    def __post_init__(self) -> None:
        if self.chamber_count < 2:
            raise RevolverError("A revolver needs at least 2 chambers.")
    def spin(self) -> None:
        self._loaded_index = secrets.randbelow(self.chamber_count)
        self._position = 0
        self._fired = False

    def pull_trigger(self) -> bool:
        if self._loaded_index is None:
            raise RevolverError("Cannot pull the trigger before spinning.")
        if self._fired:
            raise RevolverError(
                "The bullet has already been discharged. Spin again."
            )
        is_hit = self._position == self._loaded_index
        if is_hit:
            self._fired = True
        self._position = (self._position + 1) % self.chamber_count
        return is_hit
    @property
    def remaining_chambers(self) -> int:
        if self._loaded_index is None:
            return self.chamber_count
        distance = (self._loaded_index - self._position) % self.chamber_count
        return distance
    @property
    def survival_probability(self) -> float:
        if self._loaded_index is None:
            return (self.chamber_count - 1) / self.chamber_count
        chambers_left = self.chamber_count - self._position
        if chambers_left <= 0:
            return 1.0
        if self.remaining_chambers == 0:
            return 1.0
        return (chambers_left - 1) / chambers_left
    def is_ready(self) -> bool:
        return self._loaded_index is not None and not self._fired
