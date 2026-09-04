from .catalog import DatasetInfo
from .common import CamelModel


class HealthResponse(CamelModel):
    status: str
    version: str
    dataset: DatasetInfo
    program_count: int
    department_count: int
    active_sessions: int
