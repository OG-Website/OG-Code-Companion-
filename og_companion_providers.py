"""Explicit hosted model connections; credentials exist only in this process."""
import ipaddress
import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

PRESETS = {
    'OpenAI (Responses)': ('https://api.openai.com/v1', 'responses'),
    'Anthropic (Messages)': ('https://api.anthropic.com/v1', 'anthropic'),
    'Gemini (OpenAI-compatible)': ('https://generativelanguage.googleapis.com/v1beta/openai', 'chat'),
    'Custom (OpenAI-compatible)': ('', 'chat'),
    'Custom (Responses-compatible)': ('', 'responses'),
}
_CREDENTIALS = {}


def hosted_endpoint(value):
    value=value.strip().rstrip('/');parsed=urlsplit(value)
    if (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.hostname.lower()=='localhost'):
        raise ValueError('Use a public HTTPS API base URL without credentials, a query or a fragment. Local services use Add service URL.')
    try:
        address=ipaddress.ip_address(parsed.hostname)
    except ValueError:address=None
    if address is not None and not address.is_global:raise ValueError('Hosted API connections require a public address. Use the local service controls for local models.')
    # Validate the port now, without opening a connection or sending a key.
    try:parsed.port
    except ValueError as error:raise ValueError('The API port is invalid.') from error
    return value


def configure_hosted(provider, endpoint, model, key, auth='Bearer'):
    if provider not in PRESETS:raise ValueError('Choose a supported API protocol.')
    if not model.strip() or len(model)>300 or any(c in model for c in '\r\n'):raise ValueError('Enter the model ID supplied by your provider.')
    if not key.strip() or any(c in key for c in '\r\n'):raise ValueError('Enter an API key for this session.')
    if auth not in ('Bearer','api-key','x-api-key'):raise ValueError('Unsupported authentication header.')
    endpoint=hosted_endpoint(endpoint)
    credential_id=uuid.uuid4().hex;_CREDENTIALS[credential_id]=key.strip()
    return {'name':model.strip(),'endpoint':endpoint,'provider':provider,'protocol':PRESETS[provider][1],
            'credential_id':credential_id,'auth':auth,'hosted':True,'kind':'llm'}


def forget_hosted(record):
    _CREDENTIALS.pop(record.get('credential_id'),None)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise RuntimeError('The API redirected the request. Check the base URL; credentials were not forwarded to the redirect destination.')


def hosted_generate(record, system, prompt, max_tokens):
    """One request per invocation; errors never reproduce response bodies or keys."""
    base=hosted_endpoint(record['endpoint']);key=_CREDENTIALS.get(record.get('credential_id'))
    if not key:raise RuntimeError('The API key is no longer available. Add the API model again for this session.')
    protocol=record['protocol'];headers={'Content-Type':'application/json','Accept':'application/json','User-Agent':'OG-Code-Companion/2.4'}
    if protocol=='anthropic':
        headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
        path='/messages';payload={'model':record['name'],'max_tokens':max_tokens,'system':system,'messages':[{'role':'user','content':prompt}]}
    else:
        auth=record.get('auth','Bearer');headers['Authorization' if auth=='Bearer' else auth]=('Bearer '+key) if auth=='Bearer' else key
        if protocol=='responses':
            path='/responses';payload={'model':record['name'],'instructions':system,'input':prompt,'max_output_tokens':max_tokens,'store':False}
        elif protocol=='chat':
            path='/chat/completions';payload={'model':record['name'],'stream':False,'max_tokens':max_tokens,'messages':[{'role':'system','content':system},{'role':'user','content':prompt}]}
        else:raise ValueError('Unsupported hosted API protocol.')
    request=Request(base+path,data=json.dumps(payload).encode('utf-8'),headers=headers,method='POST')
    try:
        with build_opener(NoRedirects()).open(request,timeout=300) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise RuntimeError('The API response exceeded the 2 MB limit. Your existing code is retained.')
        result=json.loads(raw)
    except HTTPError as error:
        error.close()
        reason={401:'Check the API key.',403:'Check account/model permissions.',404:'Check the API base URL and model ID.',429:'Check quota, billing and rate limits.'}.get(error.code,'Check the provider status and the selected protocol.')
        raise RuntimeError(f'Hosted API returned HTTP {error.code}. {reason} No automatic network retry was made; your code is retained.') from None
    except (TimeoutError,URLError):raise RuntimeError('The hosted API request failed or timed out. Check the provider and connection. No automatic network retry was made; your code is retained.') from None
    except (ValueError,OSError):raise RuntimeError('The hosted API returned an unreadable response. Check the provider/protocol. Your code is retained.') from None
    try:
        if protocol=='responses':
            text='\n'.join(part['text'] for item in result.get('output',[]) if item.get('type')=='message' for part in item.get('content',[]) if part.get('type')=='output_text')
            finish='length' if result.get('status')=='incomplete' else result.get('status')
        elif protocol=='anthropic':
            text='\n'.join(part['text'] for part in result['content'] if part.get('type')=='text')
            finish='length' if result.get('stop_reason')=='max_tokens' else result.get('stop_reason')
        else:
            choice=result['choices'][0];text=choice['message']['content'];finish=choice.get('finish_reason')
        if not isinstance(text,str) or not text.strip():raise ValueError('Empty output')
    except (KeyError,IndexError,TypeError,ValueError,AttributeError):raise RuntimeError('The API returned no usable text code. Check the model and selected protocol; your code is retained.') from None
    return {'response':text,'done_reason':finish}
