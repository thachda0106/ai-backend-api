---
phase: 4
plan: 5
wave: 3
depends_on: [1, 2, 3, 4]
files_modified:
  - app/main.py
  - app/container.py
autonomous: true

must_haves:
  truths:
    - "app.main uses register_routers() to include all API routers"
    - "Middleware is added in correct order (logging first, rate limit second)"
    - "Container wiring includes the new router modules"
    - "Health endpoint moves to a proper router or stays in main"
---

# Plan 4.5: App Factory Wiring & Health Endpoint

## Objective
Wire everything together in `app/main.py` — register routers, add middleware stack, update DI container wiring, and refine the health endpoint. This is the integration plan that makes all previous plans functional.

## Context
- @app/main.py — Existing app factory (has lifespan, basic health check, global exception handler)
- @app/container.py — DI container (wiring_config references "app.api.routers")
- @app/api/routers/__init__.py — register_routers(app) (from Plan 4.3/4.4)
- @app/api/middleware/__init__.py — Middleware classes (from Plan 4.2)
- @app/api/middleware/error_handler.py — register_exception_handlers(app) (from Plan 4.2)

## Tasks

<task type="auto">
  <name>Wire routers, middleware, and refine app factory</name>
  <files>
    app/main.py
  </files>
  <action>
    Update `create_app()` in `app/main.py`:

    1. **Remove the inline health check** — replace with a proper health router:
       - Create `app/api/routers/health.py` with a `GET /health` endpoint that checks:
         - App status: "healthy"
         - Version from settings or package
         - Uptime (optional)
       - OR keep it inline if simpler — judgment call

    2. **Remove the inline global exception handler** — replaced by `register_exception_handlers(app)` from Plan 4.2

    3. **Register routers:**
       ```python
       from app.api.routers import register_routers
       register_routers(app)
       ```

    4. **Add middleware (order matters — last added = first executed):**
       ```python
       from app.api.middleware.request_logging import RequestLoggingMiddleware
       from app.api.middleware.rate_limit import RateLimitMiddleware

       # Rate limit first (outer), then logging (inner)
       app.add_middleware(RateLimitMiddleware, rate_limiter=container.rate_limiter())
       app.add_middleware(RequestLoggingMiddleware)
       ```
       Note: Starlette executes middleware in reverse-add order, so add logging AFTER rate limit
       so that logging wraps rate limit (logging sees all requests, including rate limited ones).

    5. **Register exception handlers:**
       ```python
       from app.api.middleware.error_handler import register_exception_handlers
       register_exception_handlers(app)
       ```

    6. **Keep the lifespan handler** — it already handles startup/shutdown correctly.
  </action>
  <verify>python -m poetry run python -c "from app.main import create_app; app = create_app(); routes = [r.path for r in app.routes]; print(f'Routes: {routes}'); assert '/documents' in str(routes) or '/documents/' in str(routes); assert '/search' in str(routes) or '/search/' in str(routes); assert '/chat' in str(routes) or '/chat/' in str(routes); print('All API routes registered')"</verify>
  <done>All routers, middleware, and exception handlers wired in create_app()</done>
</task>

<task type="auto">
  <name>Update container wiring configuration</name>
  <files>
    app/container.py
  </files>
  <action>
    Update the `wiring_config` in `Container` to include all API modules:

    ```python
    wiring_config = containers.WiringConfiguration(
        modules=[
            "app.api.routers.documents",
            "app.api.routers.search",
            "app.api.routers.chat",
            "app.api.dependencies.container",
            "app.main",
        ],
    )
    ```

    This ensures dependency-injector can wire `@inject` decorators in these modules.
    Note: Since we're using explicit `request.app.state.container` access pattern
    rather than `@inject`, this may be optional — but keeping it ensures future
    compatibility and avoids subtle bugs.
  </action>
  <verify>python -m poetry run python -c "from app.container import Container; c = Container(); print(f'Wiring modules: {c.wiring_config.modules}')"</verify>
  <done>Container wiring includes all API modules</done>
</task>

## Success Criteria
- [ ] `create_app()` registers all routers (documents, search, chat, health)
- [ ] Middleware stack: logging → rate limit → route handler
- [ ] Domain exceptions are mapped to HTTP errors
- [ ] Container wiring includes API modules
- [ ] Application starts without import errors: `python -m poetry run python -c "from app.main import app; print('App OK')"`
