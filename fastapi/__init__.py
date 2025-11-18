import inspect
import json
import re
from typing import Any, Callable, Dict, Optional


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class UploadFile:
    def __init__(self, filename: str, file):
        self.filename = filename
        self.file = file


class Depends:
    def __init__(self, dependency=None):
        self.dependency = dependency


def File(default=None):
    return default


class FastAPI:
    def __init__(self, title: str | None = None):
        self.title = title
        self.routes = []

    def _register(self, method: str, path: str, func: Callable):
        pattern = re.sub(r"{([^}]+)}", r"(?P<\1>[^/]+)", path)
        regex = re.compile(f"^{pattern}$")
        self.routes.append({"method": method.upper(), "path": path, "regex": regex, "func": func})
        return func

    def get(self, path: str, **kwargs):
        def decorator(func):
            return self._register("GET", path, func)

        return decorator

    def post(self, path: str, **kwargs):
        def decorator(func):
            return self._register("POST", path, func)

        return decorator

    def delete(self, path: str, **kwargs):
        def decorator(func):
            return self._register("DELETE", path, func)

        return decorator

    def mount(self, *args, **kwargs):
        # mounting static files is a no-op in this minimal stub
        return None

    def _handle_request(self, method: str, path: str, *, json_body=None, form_data=None, files=None):
        path_only, _, query_string = path.partition("?")
        query_params = dict(pair.split("=", 1) for pair in query_string.split("&") if pair) if query_string else {}
        for route in self.routes:
            if route["method"] != method.upper():
                continue
            match = route["regex"].match(path_only)
            if not match:
                continue
            func = route["func"]
            path_params = {k: int(v) if v.isdigit() else v for k, v in match.groupdict().items()}
            try:
                merged_body = {}
                if query_params:
                    merged_body.update(query_params)
                if json_body is not None:
                    merged_body.update(json_body)
                elif form_data is not None:
                    merged_body.update(form_data)
                return self._execute(func, path_params, json_body=merged_body or None, form_data=None, files=files)
            except HTTPException as exc:
                return Response(status_code=exc.status_code, content=json.dumps({"detail": exc.detail}).encode(), headers={"content-type": "application/json"})
        return Response(status_code=404, content=b"{\"detail\": \"Not Found\"}", headers={"content-type": "application/json"})

    def _execute(self, func: Callable, path_params: Dict[str, Any], *, json_body=None, form_data=None, files=None):
        signature = inspect.signature(func)
        kwargs: Dict[str, Any] = {}
        cleanup_callbacks = []
        body_data = json_body if json_body is not None else form_data or {}
        for name, param in signature.parameters.items():
            ann = param.annotation
            if name in path_params:
                kwargs[name] = path_params[name]
                continue
            if name in (body_data or {}):
                value = body_data[name]
                if ann is int:
                    try:
                        value = int(value)
                    except Exception:
                        pass
                kwargs[name] = value
                continue
            ann = param.annotation
            if ann and hasattr(ann, "from_dict") and json_body is not None:
                try:
                    kwargs[name] = ann.from_dict(json_body)
                except Exception as exc:  # validation failed
                    raise HTTPException(status_code=400, detail=str(exc))
                continue
            if ann and hasattr(ann, "from_form") and form_data is not None:
                try:
                    kwargs[name] = ann.from_form(form_data)
                except Exception as exc:
                    raise HTTPException(status_code=400, detail=str(exc))
                continue
            if files and (ann is UploadFile or (hasattr(ann, "__args__") and UploadFile in getattr(ann, "__args__", []))):
                file_info = files.get(name)
                if file_info:
                    filename, file_obj, _ctype = file_info
                    kwargs[name] = UploadFile(filename, file_obj)
                    continue
            if param.default is not inspect._empty:
                default_value = param.default
                if isinstance(default_value, Depends) and default_value.dependency:
                    dep = default_value.dependency()
                    if hasattr(dep, "__enter__"):
                        value = dep.__enter__()
                        cleanup_callbacks.append(lambda d=dep: d.__exit__(None, None, None))
                    else:
                        value = dep
                    kwargs[name] = value
                else:
                    kwargs[name] = default_value
                continue
        try:
            result = func(**kwargs)
            return Response.from_result(result)
        finally:
            for callback in cleanup_callbacks:
                callback()


class Response:
    def __init__(self, status_code: int, content: bytes, headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}

    @property
    def text(self):
        try:
            return self.content.decode()
        except Exception:
            return str(self.content)

    def json(self):
        return json.loads(self.content or b"{}")

    @classmethod
    def from_result(cls, value: Any):
        if isinstance(value, Response):
            return value
        if isinstance(value, (bytes, bytearray)):
            return cls(status_code=200, content=bytes(value), headers={})
        if isinstance(value, dict) or isinstance(value, list):
            return cls(status_code=200, content=json.dumps(value).encode(), headers={"content-type": "application/json"})
        if value is None:
            return cls(status_code=200, content=b"null", headers={"content-type": "application/json"})
        return cls(status_code=200, content=str(value).encode())


# submodule imports
from .responses import FileResponse
from .staticfiles import StaticFiles
