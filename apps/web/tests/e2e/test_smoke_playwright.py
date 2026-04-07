"""Legacy entrypoint kept intentionally thin.

The former 800+ line smoke suite was split into focused modules:
- test_dashboard.py
- test_subscriptions.py
- test_settings.py
- test_jobs_artifacts.py

Shared runtime/fixture logic now lives in:
- conftest.py
- support/runtime_utils.py
- support/mock_api.py
- support/assertions.py
"""
