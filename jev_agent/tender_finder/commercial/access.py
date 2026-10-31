"""Fresh per-origin robots gate for the public reader; no identity switching.

Uses inherited proxy/CA, no cookies/login, bounded bodies, no cross-host robots
redirects. Network/5xx/HTML challenge failures are unknown permission, not Allow.
RFC-style wildcard/end matching and longest Allow precedence are deterministic.
"""
from dataclasses import dataclass
import hashlib
import re
import time
from urllib.parse import urlsplit,urljoin,quote
import urllib.request
import urllib.error

from .model import public_url

USER_AGENT='StroykaJev/3.0'


@dataclass(frozen=True)
class Decision:
    allowed: bool
    status: str
    robots_sha256: str | None = None
    http_status: int | None = None

    def __post_init__(self):
        if (type(self.allowed) is not bool or self.status not in ('allowed','robots_disallow','policy_not_verified')
                or self.allowed!=(self.status=='allowed')
                or self.robots_sha256 is not None and not re.fullmatch('[a-f0-9]{64}',self.robots_sha256)):
            raise ValueError('consistent_public_access_decision_required')


def normalize(value):
    # Decode only unreserved percent escapes; reserved octets retain their
    # encoded identity. Non-ASCII UTF-8 is compared as URI octets.
    def escaped(match):
        char=chr(int(match[1],16))
        return char if char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~' else '%'+match[1].upper()
    return quote(re.sub(r'%([0-9a-fA-F]{2})',escaped,value),safe="/%:?&=;,+@!()[]$*'-._~")


def matches(pattern,value):
    anchored=pattern.endswith('$');pattern=pattern[:-1] if anchored else pattern
    if not anchored:pattern+='*'
    pattern=re.sub(r'\*+','*',pattern)
    i=j=0;star=-1;mark=0
    while i<len(value):
        if j<len(pattern) and pattern[j]==value[i]:i+=1;j+=1
        elif j<len(pattern) and pattern[j]=='*':star=j;j+=1;mark=i
        elif star>=0:mark+=1;i=mark;j=star+1
        else:return False
    while j<len(pattern) and pattern[j]=='*':j+=1
    return j==len(pattern)


class Rules:
    def __init__(self,text):
        if not isinstance(text,str) or len(text.encode())>128*1024 or '<html' in text.casefold():
            raise ValueError('bounded_plain_robots_required')
        self.groups=[];agents=[];rules=[];seen_content=False;recognized=False
        def flush():
            if agents:self.groups.append((tuple(agents),tuple(rules)))
            agents.clear();rules.clear()
        for raw in text.splitlines():
            line=raw.split('#',1)[0].strip()
            if not line:
                if agents:flush()
                continue
            seen_content=True
            if ':' not in line:raise ValueError('robots_text_not_verified')
            key,value=line.split(':',1);key=key.strip().casefold();value=value.strip()
            if key=='user-agent':
                if rules:flush()
                if value:agents.append(value.casefold());recognized=True
            elif key in ('allow','disallow') and agents and value:
                if len(value)>2048:raise ValueError('robots_rule_limit')
                rules.append((normalize(value),key=='allow'))
            elif key=='sitemap' and public_url(value):recognized=True
        flush()
        if seen_content and not recognized:raise ValueError('robots_text_not_verified')
        if len(self.groups)>1000 or sum(len(group[1]) for group in self.groups)>4000:
            raise ValueError('robots_group_limit')

    def allowed(self,url,agent=USER_AGENT):
        agent=agent.casefold();selected=[];specificity=-1
        for agents,rules in self.groups:
            length=max((0 if item=='*' else len(item) for item in agents if item=='*' or item in agent),default=-1)
            if length>specificity:specificity=length;selected=list(rules)
            elif length==specificity and length>=0:selected.extend(rules)
        parsed=urlsplit(url);path=normalize(parsed.path or '/')
        if parsed.query:path+='?'+normalize(parsed.query)
        applicable=[(len(pattern.replace('*','').rstrip('$').encode()),allow)
                    for pattern,allow in selected if matches(pattern,path)]
        return max(applicable,default=(-1,True))[1]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def fetch_robots(url):
    request=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'text/plain'})
    opener=urllib.request.build_opener(NoRedirect)
    try:response=opener.open(request,timeout=12)
    except urllib.error.HTTPError as error:response=error
    with response:
        return response.code,response.headers.get('Location'),response.read(128*1024+1)


class PublicAccess:
    def __init__(self,hosts,*,fetch=fetch_robots,monotonic=time.monotonic):
        if not callable(fetch) or not callable(monotonic):raise ValueError('protected_robots_transport_required')
        self.hosts=frozenset(hosts);self.fetch=fetch;self.monotonic=monotonic;self.cache={}

    def check(self,url):
        if not public_url(url) or urlsplit(url).hostname not in self.hosts:
            return Decision(False,'policy_not_verified')
        parsed=urlsplit(url);origin=parsed.scheme+'://'+parsed.netloc;now=self.monotonic()
        cached=self.cache.get(origin)
        if cached and cached[0]>now:policy=cached[1]
        else:
            policy=self._load(origin+'/robots.txt')
            self.cache[origin]=(now+(300 if isinstance(policy,Rules) else 30),policy)
        if isinstance(policy,Decision):return policy
        allowed=policy.allowed(url)
        return Decision(allowed,'allowed' if allowed else 'robots_disallow',getattr(policy,'digest',None),200)

    def _load(self,url):
        try:
            for _ in range(3):
                code,location,body=self.fetch(url)
                if code in (301,302,303,307,308):
                    target=urljoin(url,location or '')
                    if (not public_url(target) or urlsplit(target).netloc!=urlsplit(url).netloc
                            or urlsplit(target).path!='/robots.txt' or urlsplit(target).query):
                        return Decision(False,'policy_not_verified',http_status=code)
                    url=target;continue
                if code in (404,410):return Decision(True,'allowed',http_status=code)
                if code in (401,403):return Decision(False,'robots_disallow',http_status=code)
                if code!=200 or type(body) is not bytes or len(body)>128*1024:
                    return Decision(False,'policy_not_verified',http_status=code)
                rules=Rules(body.decode('utf-8-sig'));rules.digest=hashlib.sha256(body).hexdigest()
                return rules
        except Exception:pass
        return Decision(False,'policy_not_verified')
