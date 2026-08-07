"""Fixed E6 approval errors shared by orchestration and storage."""


class BudgetAdjustmentApprovalError(RuntimeError):
    """Fixed-code approval failure safe to map at a later HTTP boundary."""

    def __init__(self, code):
        self.code = str(code)
        super().__init__(self.code)


__all__ = ["BudgetAdjustmentApprovalError"]
