"""Reviewed estimate-row balance transfer diagnostics and inert plans.

Keep the package import-pure.  Read-only policy consumers must not load the
route registration graph (and its writer dependencies) merely by importing a
submodule such as :mod:`policy`.
"""

__all__ = ["register_estimate_row_transfer_module"]


def __getattr__(name):
    if name != "register_estimate_row_transfer_module":
        raise AttributeError(name)
    from .routes import register_estimate_row_transfer_module

    return register_estimate_row_transfer_module
