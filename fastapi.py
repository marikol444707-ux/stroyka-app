class HTTPException(Exception):
    def __init__(self, status_code=500, detail=None):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")
