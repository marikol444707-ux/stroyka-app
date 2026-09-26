
class Depends:
    def __init__(self, f=None):
        pass

class Header:
    def __init__(self, default=None, alias=None):
        pass

class HTTPException(Exception):
    def __init__(self, status_code=400, detail=None):
        self.status_code = status_code
        super().__init__(detail)
