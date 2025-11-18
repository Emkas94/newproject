import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import cgi

from app.main import app


class ChatRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        response = app._handle_request("GET", urlparse(self.path).path)
        self._write_response(response)

    def do_POST(self):
        content_type = self.headers.get("Content-Type", "")
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        json_body = None
        form_data = None
        files = None

        if "application/json" in content_type:
            json_body = json.loads(body.decode() or "{}")
        elif content_type.startswith("multipart/form-data"):
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(length),
            }
            fs = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=environ, keep_blank_values=True)
            form_data = {key: fs.getvalue(key) for key in fs.keys() if not fs[key].filename}
            files = {}
            for key in fs.keys():
                field = fs[key]
                if getattr(field, "filename", None):
                    files[key] = (field.filename, field.file, field.type)
        else:
            form_data = parse_qs(body.decode())
            form_data = {k: v[0] if isinstance(v, list) else v for k, v in form_data.items()}

        response = app._handle_request("POST", urlparse(self.path).path, json_body=json_body, form_data=form_data, files=files)
        self._write_response(response)

    def _write_response(self, response):
        self.send_response(response.status_code)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(response.content)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8000), ChatRequestHandler)
    print("Serving chat API on http://0.0.0.0:8000")
    server.serve_forever()
