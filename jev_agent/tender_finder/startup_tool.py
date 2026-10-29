"""Self-registering builtin adapter support for the pinned Hermes registry.

The small integration/hermes_jev_tool.py file is mounted as a root-owned Hermes
builtin. Discovery registers the schema; the live GatewayRunner is resolved only
on an actual tool call, avoiding a gateway import cycle during startup. No key,
credential generation, service start, search or send happens on module import.
"""
import os
from pathlib import Path

from .hermes_binding import bind_broker_gateway, submit_handler, verified_loaded_modules
from .settings import load_settings

NAME='jev_tender_search'
TOOLSET='hermes-telegram'
SCOPE='/opt/data'
SOCKET='/run/stroyka-jev/admission.sock'
POLICY=Path('/opt/stroyka-jev/config/bridge.json')
SCHEMA={'name':NAME,'description':
    'Поиск строительных закупок Ставропольского края через JEV. Передай request_json '
    'версии 2: уникальный request_id, region="Ставропольский край", sources '
    '(eis/commercial), topics; при необходимости фильтры цены/сроков. Не передавай '
    'company_id, получателя, ключи или команды. queued подтверждает только постановку '
    'в очередь, а не завершённый поиск; результаты доставляются отдельно.',
    'parameters':{'type':'object','properties':{'request_json':{'type':'string','maxLength':32768}},
                  'required':['request_json'],'additionalProperties':False}}


def handle(args,**_ignored):
    try:
        settings=load_settings(POLICY,trusted_root=Path('/opt/stroyka-jev'))
        if (settings.queue.writer_uid!=0 or settings.gateway_uid!=os.geteuid()
                or settings.owner.profile is not None):
            raise ValueError('explicit_default_profile_broker_policy_required')
        modules=verified_loaded_modules()
        runner=modules['gateway.run']._gateway_runner_ref()
        runtime=bind_broker_gateway(runner,settings.owner,SOCKET)
        return submit_handler(runtime)(args)
    except Exception:
        return {'queued':False,'reason':'jev_gateway_not_ready'}


class StartupRegistration:
    """AST-visible registry.register() wrapper with atomic collision prevention.

    The pinned discovery scanner only recognizes top-level register expressions,
    not a register inside `with`. The wrapper keeps the real registry's RLock
    across lookup+registration; an existing handler is never replaced.
    """
    def __init__(self,registry):self._registry=registry

    def register(self):
        with self._registry._lock:
            if self._registry.get_entry(NAME,scope=SCOPE) is not None:
                raise ValueError('existing_jev_registration_preserved')
            # The pinned Telegram bundle merges registry entries registered
            # under its own name. A separate 'jev' group is not in that bundle.
            self._registry.register(name=NAME,toolset=TOOLSET,schema=SCHEMA,handler=handle,
                                    scope=SCOPE,override=False,execution_timeout=5)
