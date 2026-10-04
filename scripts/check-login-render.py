"""Validate saved real Keycloak HTML without printing tokens or form actions."""
from html.parser import HTMLParser
from pathlib import Path
import argparse
import re

class Login(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs=set()
        self.challenge=None
        self.post_form=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if tag=='input':
            self.inputs.add(a.get('name'))
        if tag=='form' and a.get('method','').lower()=='post' and a.get('action'):
            self.post_form=True
        if 'data-avan-captcha' in a:
            self.challenge=a

def validate(html):
    if len(html)>1_000_000:
        raise ValueError('Unexpectedly large login response')
    if any(message in html for message in ('An internal server error has occurred','We are sorry','سرویس امنیتی آوان موقتاً آماده نیست')):
        raise ValueError('Login or security bridge error page')
    page=Login()
    page.feed(html)
    if 'ورود به آوان' not in html or not page.post_form or not {'username','password','avan-antibot'} <= page.inputs:
        raise ValueError('Expected AVAN credential form missing')
    challenge=page.challenge or {}
    for key in ('data-challenge','data-signature'):
        if not re.fullmatch(r'[0-9a-fA-F]{64}', challenge.get(key,'')):
            raise ValueError('Local anti-bot challenge unavailable')
    if challenge.get('data-action')!='avan-login' or not challenge.get('data-salt'):
        raise ValueError('Invalid login challenge scope')
    for key in ('data-max-number','data-expires-in'):
        if not challenge.get(key,'').isdigit() or int(challenge[key])<=0:
            raise ValueError('Invalid challenge bounds')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html_file',type=Path)
    args=parser.parse_args()
    # Bound input read as well as parser work.
    with args.html_file.open(encoding='utf-8') as handle:
        validate(handle.read(1_000_001))
    print('Real login form and local challenge rendered; credential/OTP login is a separate gate.')
