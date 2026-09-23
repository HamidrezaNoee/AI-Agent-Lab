"""Publisher-only public-key pinning, usable on Linux and Windows."""
import argparse
import hashlib
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--public-key',required=True)
args=p.parse_args()
raw=Path(args.public_key).read_text(encoding='ascii').replace('\r\n','\n').strip().encode('ascii')
if not raw.startswith(b'-----BEGIN PUBLIC KEY-----') or b'PRIVATE KEY' in raw:
    raise SystemExit('Choose the issuer public key only')
root=Path(__file__).resolve().parent.parent
(root/'commercial/licensing/publisher-key.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n',encoding='ascii')
print('Public-key fingerprint pinned. Rebuild the customer image.')
