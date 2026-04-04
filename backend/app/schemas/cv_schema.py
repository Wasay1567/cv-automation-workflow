from pydantic import BaseModel
from typing import List, Optional


class Skill(BaseModel):
    name: str


class Experience(BaseModel):
    company: str
    to_date: Optional[str] = None
    from_date: Optional[str] = None
    date: Optional[str] = None
    title: str
    description: List[str]


class Education(BaseModel):
    institution: str
    to_date: Optional[str] = None
    from_date: Optional[str] = None
    date: Optional[str] = None
    degree: str 
    majors: Optional[str] = None
    description: Optional[str] = None


class CVRequest(BaseModel):
    student_id: str
    name: str
    profession: str
    phone: str
    email: str
    address: str
    about_me: str
    profile_image_url: Optional[str] = None
    skills: List[Skill]
    languages: Optional[List[dict]] = None
    certificates: Optional[List[str]] = None
    personality_score: Optional[int] = None
    experience: List[Experience]
    education: List[Education]