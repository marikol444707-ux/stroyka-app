from pydantic import BaseModel


class TimesheetModel(BaseModel):
    staffId: int
    day: str
