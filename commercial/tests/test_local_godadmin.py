import httpx
from commercial.local_godadmin import human_accounts

def test_cleanup_excludes_infrastructure_service_accounts():
    def handler(request):
        return httpx.Response(200,json=[
            {'id':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','username':'other'},
            {'id':'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb','username':'service-account-avan-provisioner','serviceAccountClientId':'avan-provisioner'}])
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert human_accounts(client,{'Authorization':'Bearer test'})==['aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa']
