"""Explicit root FD bootstrap for v3; no service installation or key creation."""
from pathlib import Path
from ..broker_service import _main
from .runtime_config import load_runtime,initialize_commercial_host

SOCKET=Path('/run/stroyka-jev/commercial.sock')


def main(argv=None):
    return _main(argv,initialize_commercial_host,lambda listener,host,stop:host.serve(listener,stop),
                 settings_loader=lambda path:load_runtime(path).bridge,listener_path=SOCKET)


if __name__=='__main__':raise SystemExit(main())
