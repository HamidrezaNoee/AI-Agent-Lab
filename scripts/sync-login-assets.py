"""Synchronize canonical admin scene into the Docker-built Keycloak theme."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
source=root/'commercial/web/admin'
target=root/'infra/keycloak/themes/avan/login/resources'
for src,dest in [('login-scene.js','js/login-scene.js'),('login-scene.css','css/login-scene.css')]:
    shutil.copyfile(source/src,target/dest)
for file in (source/'scene-data').glob('*.webp'):
    shutil.copyfile(file,target/'scene-data'/file.name)
print('Login scene synchronized.')
