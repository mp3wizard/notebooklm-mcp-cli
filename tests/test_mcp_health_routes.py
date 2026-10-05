from starlette.routing import Route

from notebooklm_tools.mcp.server import mcp


def test_health_routes_support_conventional_probe_paths_and_head():
    app = mcp.http_app()
    health_routes = {
        route.path: route
        for route in app.routes
        if isinstance(route, Route) and route.path in {"/health", "/healthz"}
    }

    assert set(health_routes) == {"/health", "/healthz"}
    for route in health_routes.values():
        assert "GET" in route.methods
        assert "HEAD" in route.methods
