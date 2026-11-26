from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    file: str
    field: str
    rule: str
    message: str
    severity: str = "ERROR"

    def format(self) -> str:
        return (
            f"[{self.file}] {self.severity} | "
            f"field={self.field} | rule={self.rule} | {self.message}"
        )