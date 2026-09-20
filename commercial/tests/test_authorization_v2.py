"""Offline v2 role and SQL-shape tests. No real ProcessMaker/SQL calls."""
import unittest
from uuid import UUID
from commercial.security import Principal
from commercial.authorization_v2 import visible_meetings_v2

class Cursor:
    def __init__(self,role,meetings):self.role=role;self.meetings=meetings;self.sqls=[]
    def execute(self,sql,*params):
        self.sqls.append((sql,params))
        self.current=[(self.role,"Test User","pm-u","pm-test",1)] if "LEFT JOIN AgentProduct.UserDirectory" in sql else self.meetings
        return self
    def fetchone(self):return self.current[0] if self.current else None
    def fetchall(self):return self.current
class Con:
    def __init__(self,role,meetings):self.c=Cursor(role,meetings)
    def cursor(self):return self.c

class AuthorizationV2Tests(unittest.TestCase):
    def setUp(self):self.p=Principal(UUID("11111111-1111-4111-8111-111111111111"),"person")
    def test_expert_uses_hierarchy_authorizer(self):
        c=Con("Expert",[(1,"M1","t","Open")]);visible_meetings_v2(c,self.p)
        sql=c.c.sqls[-1][0];self.assertIn("fn_can_view_meeting",sql);self.assertNotIn("MeetingGrant g",sql)
    def test_manager_uses_same_server_side_scope_function(self):
        c=Con("Manager",[(1,"M1","t","Open")]);visible_meetings_v2(c,self.p)
        self.assertIn("fn_can_view_meeting",c.c.sqls[-1][0])
    def test_sysadmin_has_tenant_scope_but_never_cross_tenant(self):
        c=Con("SysAdmin",[(1,"M1","t","Open")]);visible_meetings_v2(c,self.p)
        sql,params=c.c.sqls[-1];self.assertIn("m.TenantID=?",sql);self.assertNotIn("fn_can_view_meeting",sql)
        self.assertEqual(params,(str(self.p.tenant_id),))
    def test_godadmin_requires_explicit_content_grant(self):
        c=Con("GodAdmin",[(1,"M1","t","Open")]);visible_meetings_v2(c,self.p)
        sql=c.c.sqls[-1][0];self.assertIn("MeetingGrant g",sql);self.assertIn("g.SubjectID=?",sql)

if __name__=="__main__":unittest.main()
