import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('login_probe',Path(__file__).resolve().parents[2]/'scripts/check-login-render.py')
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
HTML='''ورود به آوان<form method="post" action="/login"><input name="username"><input name="password"><input name="avan-antibot"><div data-avan-captcha data-action="avan-login" data-salt="salt" data-challenge="HASH" data-signature="HASH" data-max-number="75000" data-expires-in="120"></div></form>'''.replace('HASH','a'*64)
def test_valid_form_and_challenge():
    probe.validate(HTML)
@pytest.mark.parametrize('html',[
    'We are sorry... An internal server error has occurred.',
    HTML+'سرویس امنیتی آوان موقتاً آماده نیست',
    HTML.replace('a'*64,''), HTML.replace('avan-login','other-action'),
    HTML.replace('name="password"','name="other"'),
    HTML.replace('data-expires-in="120"','data-expires-in="0"'),
    HTML.replace('method="post"','method="get"'), 'x'*1_000_001,
])
def test_invalid_render_fails(html):
    with pytest.raises(ValueError):
        probe.validate(html)
