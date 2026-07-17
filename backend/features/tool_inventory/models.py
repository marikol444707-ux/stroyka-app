from typing import Optional

from pydantic import BaseModel


class ToolModel(BaseModel):
    name: str
    inventoryNumber: str = ""
    cost: float = 0
    status: str = "На складе"
    location: str = "Основной склад"
    project: str = ""
    masterId: Optional[int] = None
    masterName: str = ""
    issueType: str = ""
    photoUrl: str = ""
    notes: str = ""


class ToolHistoryModel(BaseModel):
    toolId: int
    toolName: str
    action: str
    fromLocation: str = ""
    toLocation: str = ""
    masterName: str = ""
    project: str = ""
    issueType: str = ""
    condition: str = ""
    date: str = ""
    createdBy: str = ""


class InventoryModel(BaseModel):
    project: str
    date: str
    createdBy: str
    notes: str = ""


class InventoryItemModel(BaseModel):
    inventoryId: int
    materialName: str
    unit: str
    expected: float
    actual: float
    difference: float
    notes: str = ""
