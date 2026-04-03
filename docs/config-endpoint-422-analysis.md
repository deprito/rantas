# Config Endpoint 422 Error — Root Cause Analysis

**Date:** 2026-02-18  
**Endpoint:** `GET /api/config`  
**Symptom:** 422 Unprocessable Entity when calling the endpoint without query parameters

---

## Root Cause

A **FastAPI bug with `Annotated` type aliases** when used with callable class dependencies.

### The Setup

A `PermissionChecker` class was used as a FastAPI dependency (callable class with `__call__`). To simplify endpoint signatures, a type alias was created:

```python
RequireConfigView = Annotated[None, Depends(PermissionChecker("config:view"))]
```

Used in the endpoint as:

```python
@router.get("/config")
async def get_config(auth: RequireConfigView):
    ...
```

### The Bug

FastAPI's OpenAPI schema generator **incorrectly introspected** the `PermissionChecker` class's `__init__` method instead of its `__call__` method. This caused `args` and `kwargs` to appear as **required query parameters** in the generated OpenAPI schema for `/api/config`.

When the endpoint was called without these spurious parameters, FastAPI returned a **422 Unprocessable Entity** validation error.

### Evidence

The OpenAPI spec at `/openapi.json` showed `args` and `kwargs` listed as required parameters for the `/api/config` endpoint — parameters that should never have been exposed.

---

## Fix

Replaced the `Annotated` type alias with an **inline `Depends()`** call:

```python
@router.get("/config")
async def get_config(auth: None = Depends(PermissionChecker("config:view"))):
    ...
```

This ensures FastAPI correctly introspects the dependency and does not leak `__init__` parameters into the OpenAPI spec.

---

## Verification

- Rebuilt and redeployed the backend Docker image.
- Confirmed `/api/config` returns `200 OK`.
- Confirmed `/openapi.json` no longer includes `args`/`kwargs` parameters for the endpoint.

---

## Takeaway

Avoid using `Annotated` type aliases with callable class dependencies in FastAPI. Use inline `Depends()` with a default parameter value instead. This is a known quirk in how FastAPI resolves `Annotated` types with callable class instances.
