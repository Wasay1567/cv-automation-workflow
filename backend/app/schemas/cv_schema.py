from pydantic import BaseModel
from typing import List, Optional

class Skill(BaseModel):
    name: str
    level: int

class Language(BaseModel):
    name: str
    percent: int

class Experience(BaseModel):
    company: str
    date: str
    title: str
    description: str

class Education(BaseModel):
    institution: str
    date: str
    degree: str
    description: str

class CVRequest(BaseModel):
    name: str
    profession: str
    phone: str
    email: str
    address: str
    about_me: str
    profile_image_url: Optional[str] = None
    skills: List[Skill]
    languages: List[Language]
    experience: List[Experience]
    education: List[Education]