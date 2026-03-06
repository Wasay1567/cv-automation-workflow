from pydantic import BaseModel

class CVRequest(BaseModel):
    name: str
    email: str