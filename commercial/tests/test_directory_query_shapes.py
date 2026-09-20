"""Security regression for SQL emitted by the ACTIVE /v2 directory functions.

Offline SQL-shape assertions; a real database/IdP/PM run is still mandatory.
These tests prevent old MeetingGrant-only fixture paths from being reintroduced
into Expert meeting, secretary, monitoring and analytics access.
"""
import unittest
from uuid import UUID
from commercial.security import Principal
from commercial.directory_access import (
    visible_directory_meetings, directory_meeting_access,
    directory_action_report, directory_meeting_status_report,
)


class Cursor:
    def __init__(self, con):
        self.con = con
        self.rows = []
    def execute(self, sql, *params):
        self.con.log.append((sql, params))
        if "SELECT TOP (1) OrgRole,PMUserUID" in sql:
            self.rows = [(self.con.role, "a"*31+"1")]
        elif "SELECT TOP (1) OrgRole FROM AgentProduct.DirectoryUser" in sql:
            self.rows = [(self.con.role,)]
        elif "SELECT TOP (1) MeetingID,MeetingNo,MeetingTitle,MeetingStatus" in sql:
            self.rows = [(900001, "LAB-900001", "Fictional", "Closed")]
        elif "SELECT TOP (1) m.MeetingID,m.MeetingNo,m.MeetingTitle,m.MeetingStatus" in sql:
            self.rows = [(900001, "LAB-900001", "Fictional", "Closed")]
        elif "SELECT TOP (51)" in sql:
            self.rows = [(900001,"LAB-900001","Fictional","Closed")]
        elif "GROUP BY m.MeetingStatus" in sql:
            self.rows = [("Closed", 1)]
        elif "COUNT_BIG(*)" in sql:
            self.rows = [(1,0,0)]
        else:
            self.rows = []
        # Parameterized SQL only: no dynamically interpolated user/tenant values.
        assert sql.count("?") == len(params), (sql.count("?"),len(params))
        return self
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, role="Expert"):
        self.role=role
        self.log=[]
    def cursor(self):
        return Cursor(self)


class V2MeetingScopeSQLTests(unittest.TestCase):
    def setUp(self):
        self.p=Principal(UUID("11111111-1111-4111-8111-111111111111"),"lab-alice")

    def _content(self, connection):
        return [query for query, _ in connection.log
                if "AgentProduct.MeetingIndex" in query or "AgentProduct.ActionIndex" in query]

    def test_expert_lists_only_actor_subtree_and_binds_tenant(self):
        con=Connection()
        page=visible_directory_meetings(con,self.p,before_id=910100,limit=20)
        self.assertEqual(page["role"],"Expert")
        self.assertEqual(page["returned"],1)
        query, params=con.log[-1]
        self.assertIn("MeetingActor",query)
        self.assertIn("Subtree",query)
        self.assertIn("m.TenantID=?",query)
        self.assertIn("m.MeetingID<?",query)
        self.assertNotIn("MeetingGrant",query)
        self.assertEqual(params.count(str(self.p.tenant_id)),3)

    def test_manager_and_sysadmin_have_tenant_only_not_platform_scope(self):
        for role in ("Manager","SysAdmin"):
            with self.subTest(role=role):
                con=Connection(role)
                visible_directory_meetings(con,self.p)
                sql,params=con.log[-1]
                self.assertIn("m.TenantID=?",sql)
                self.assertEqual(params,(str(self.p.tenant_id),))
                self.assertNotIn("MeetingActor",sql)

    def test_single_expert_meeting_cannot_bypass_actor_via_old_grants(self):
        con=Connection()
        record=directory_meeting_access(con,self.p,900001)
        self.assertEqual(record["meeting_id"],900001)
        query,params=con.log[-1]
        self.assertIn("MeetingActor",query)
        self.assertIn("m.MeetingID=?",query)
        self.assertIn("m.TenantID=?",query)
        self.assertNotIn("MeetingGrant",query)
        self.assertEqual(params[-1],900001)

    def test_expert_action_report_is_actor_scoped(self):
        con=Connection()
        report=directory_action_report(con,self.p)
        self.assertEqual(report["actions"]["total"],1)
        query,params=con.log[-1]
        self.assertIn("MeetingActor",query)
        self.assertNotIn("MeetingGrant",query)
        self.assertIn("a.TenantID=?",query)
        self.assertEqual(params[-1],str(self.p.tenant_id))

    def test_expert_analytics_is_actor_scoped(self):
        con=Connection()
        report=directory_meeting_status_report(con,self.p)
        self.assertEqual(report["total_visible_meetings"],1)
        query,params=con.log[-1]
        self.assertIn("MeetingActor",query)
        self.assertIn("m.TenantID=?",query)
        self.assertNotIn("MeetingGrant",query)
        self.assertEqual(params[-1],str(self.p.tenant_id))


if __name__=="__main__":
    unittest.main()
