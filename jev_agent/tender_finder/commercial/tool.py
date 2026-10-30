"""Explicit, key-free Hermes tool binding. Not auto-registered or installed."""
from ..admission_broker import BrokerClient, BrokerGatewayRuntime

NAME='jev_direct_commercial_search'
SCHEMA={'name':NAME,'description':
    'Поиск прямых коммерческих строительных заказов через JEV. Передай request_json: '
    'version=3, mode="direct_commercial", уникальный request_id. По умолчанию работы '
    'в Ставропольском и Краснодарском краях, ориентир от 3000000 рублей. Можно задать '
    'regions, source_ids, minimum_rub, queries, exclude_keywords. Не передавай компанию, '
    'получателя, юрлицо, СРО, ключи, URL или команды. queued означает только приём '
    'в очередь; результаты и ограничения источников придут отдельно. Поиск не '
    'регистрируется на площадках, не отправляет заявки и не меняет сервер.',
    'parameters':{'type':'object','properties':{'request_json':{'type':'string','maxLength':32768}},
                  'required':['request_json'],'additionalProperties':False}}


def handler(gateway):
    if type(gateway) is not BrokerGatewayRuntime:raise ValueError('protected_key_free_gateway_required')
    def execute(args,**_ignored):
        if type(args) is not dict or set(args)!={'request_json'} or type(args['request_json']) is not str:
            return {'queued':False,'reason':'invalid_commercial_tool_arguments'}
        try:
            raw=args['request_json'].encode('utf-8')
            if len(raw)>32768:raise ValueError('bounded_request_required')
            return gateway.submit(raw)
        except Exception:
            return {'queued':False,'reason':'commercial_admission_not_confirmed'}
    return execute


def bind_live_gateway(runner,owner,socket_path,*,sources):
    """Use the same reviewed actual SessionSource and gateway authorization as v2.

    Host must independently bind its protocol-3 broker to this pinned process.
    No synthetic chat identifiers, current-user fallbacks or model-supplied owner.
    """
    from functools import partial
    from ..hermes_binding import verified_loaded_modules, HermesSessionBinding
    from .contract import validate_request
    modules=verified_loaded_modules()
    if type(runner) is not modules['gateway.run'].GatewayRunner:
        raise ValueError('actual_reviewed_gateway_runner_required')
    owner.validate()
    if owner.profile is not None:raise ValueError('reviewed_default_profile_required')
    binding=HermesSessionBinding(runner,modules['gateway.session_context'],modules['gateway.session'].SessionSource)
    return BrokerGatewayRuntime(owner,BrokerClient(socket_path),current_source=binding.current_source,
        authorize_source=binding.authorize_source,request_validator=partial(validate_request,sources=dict(sources)))


def register(registry,gateway,*,scope):
    """Call only from reviewed protected startup, never from model tools."""
    if scope!='/opt/data':raise ValueError('reviewed_registry_scope_required')
    execute=handler(gateway)
    with registry._lock:
        if registry.get_entry(NAME,scope=scope) is not None:
            raise ValueError('existing_commercial_registration_preserved')
        registry.register(name=NAME,toolset='hermes-telegram',schema=SCHEMA,handler=execute,
                          scope=scope,override=False,execution_timeout=5)
