from pathlib import Path
from . import Response


class FileResponse(Response):
    def __init__(self, path: str, filename: str | None = None):
        data = Path(path).read_bytes()
        super().__init__(status_code=200, content=data, headers={"content-disposition": f"attachment; filename={filename or Path(path).name}"})
