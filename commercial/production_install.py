"""Production provisioning now targets the Agent-owned AVANAgent database only.

The former EnterpriseProcess2/MTG installer has been retired. Admin routes use
agent_install.prepare and agent_install.check with the dedicated schema.
"""
from .agent_install import InstallationDenied, prepare, check
