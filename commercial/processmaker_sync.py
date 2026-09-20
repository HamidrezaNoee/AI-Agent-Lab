"""Retired experimental ProcessMaker MySQL direct-sync adapter.

The supported path is commercial.processmaker_directory.fetch_users() for
read-only ProcessMaker 3.3.x REST user snapshots, and the verified
/v2/admin/processmaker/users/sync endpoint -> isolated, audited SQL procedure.
The old module could not create a valid OIDC identity and attempted to write
using a restricted SQL reader. It must NOT run or contact an operational PM DB.
See commercial/PROCESSMAKER_ORGPORTAL_INTEGRATION_FA.md.
"""


def read_processmaker_users(*args, **kwargs):
    raise RuntimeError(
        "Legacy direct-MySQL user adapter retired: use the read-only "
        "commercial.processmaker_directory.fetch_users REST adapter."
    )


def sync_users(*args, **kwargs):
    raise RuntimeError(
        "Legacy directory writer retired: use the verified SysAdmin "
        "/v2/admin/processmaker/users/sync API and its audited SQL procedure."
    )
