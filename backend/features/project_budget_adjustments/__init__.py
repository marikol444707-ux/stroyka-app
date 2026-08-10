"""E6 approved project-budget adjustment boundaries.

Route registration is lazy so pure plan imports do not pull FastAPI, storage
or approval writers into read-only dependency graphs.
"""


__all__ = [
    "register_project_budget_adjustment_preview_module",
    "register_project_budget_adjustment_runtime_module",
]


def __getattr__(name):
    if name == "register_project_budget_adjustment_preview_module":
        from .preview_routes import (
            register_project_budget_adjustment_preview_module,
        )

        return register_project_budget_adjustment_preview_module
    if name == "register_project_budget_adjustment_runtime_module":
        from .runtime_routes import (
            register_project_budget_adjustment_runtime_module,
        )

        return register_project_budget_adjustment_runtime_module
    raise AttributeError(name)
