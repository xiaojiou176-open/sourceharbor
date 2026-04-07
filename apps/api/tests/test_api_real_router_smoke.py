from __future__ import annotations

import importlib
import sys


def _purge_api_modules() -> None:
    for module_name in list(sys.modules):
        if module_name == "apps.api.app" or module_name.startswith("apps.api.app."):
            del sys.modules[module_name]


def test_main_app_loads_real_notifications_routes_without_stub() -> None:
    # Explicitly remove potential test stub so we verify real router import path.
    sys.modules.pop("apps.api.app.routers.notifications", None)
    _purge_api_modules()

    main_module = importlib.import_module("apps.api.app.main")
    app = main_module.app
    route_paths = {getattr(route, "path", "") for route in app.routes}

    assert "/healthz" in route_paths
    assert "/api/v1/notifications/config" in route_paths
    assert "/api/v1/notifications/test" in route_paths
    assert "/api/v1/reports/daily/send" in route_paths
