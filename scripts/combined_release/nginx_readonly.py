"""Parse captured nginx -T output in memory; emit routing metadata, never raw config."""
import re
import shlex
from urllib.parse import urlsplit


def routing_facts(text):
    if len(text)>2*1024*1024:raise ValueError('NGINX_CONFIG_TOO_LARGE')
    lexer=shlex.shlex(text,posix=True,punctuation_chars='{};')
    lexer.whitespace_split=True;lexer.commenters='#'
    tokens=[]
    for token in lexer:
        tokens.extend(list(token) if token and all(c in '{};' for c in token) else [token])
    index=0
    def parse():
        nonlocal index
        nodes=[];head=[]
        while index<len(tokens):
            token=tokens[index];index+=1
            if token=='}':
                if head:raise ValueError('INVALID_NGINX_BLOCK')
                return nodes
            if token==';':nodes.append((head,None));head=[]
            elif token=='{':nodes.append((head,parse()));head=[]
            else:head.append(token)
        if head:raise ValueError('INCOMPLETE_NGINX_CONFIG')
        return nodes
    nodes=parse();result=[]
    def visit(nodes):
        for head,children in nodes:
            if head==['server'] and children is not None:
                names=[value for directive,_ in children if directive[:1]==['server_name'] for value in directive[1:]]
                if not {'stroyka26.pro','www.stroyka26.pro'}.intersection(names):continue
                record={'app_server':True,'listeners':[],'proxy_targets':[],'maintenance_return_codes':[],'dynamic_proxy_targets':0}
                for directive,_ in children:
                    if directive[:1]==['listen'] and len(directive)>1:record['listeners'].append(directive[1])
                def routes(children):
                    for directive,child in children:
                        if directive[:1]==['proxy_pass'] and len(directive)==2:
                            if '$' in directive[1]:record['dynamic_proxy_targets']+=1
                            else:
                                url=urlsplit(directive[1]);record['proxy_targets'].append({'scheme':url.scheme,'host':url.hostname,'port':url.port})
                        if directive[:1]==['return'] and len(directive)>1 and directive[1].isdigit():record['maintenance_return_codes'].append(int(directive[1]))
                        if child is not None:routes(child)
                routes(children);result.append(record)
            elif children is not None:visit(children)
    visit(nodes)
    return result
