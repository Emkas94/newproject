import json
from urllib.parse import urlencode
from . import FastAPI


class TestClient:
    def __init__(self, app: FastAPI):
        self.app = app

    def _with_params(self, path: str, params):
        if not params:
            return path
        if not isinstance(params, dict):
            return path
        query = urlencode(params)
        separator = '&' if '?' in path else '?'
        return f"{path}{separator}{query}"

    def get(self, path: str, params=None):
        full_path = self._with_params(path, params)
        response = self.app._handle_request("GET", full_path)
        return response

    def delete(self, path: str, params=None):
        full_path = self._with_params(path, params)
        response = self.app._handle_request("DELETE", full_path)
        return response

    def post(self, path: str, json=None, data=None, files=None):
        if json is not None and data is not None:
            raise ValueError("Provide either json or data, not both")
        response = self.app._handle_request("POST", path, json_body=json, form_data=data, files=files)
        return response
