import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Date,
    Enum as SQLEnum,
    Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


# ============================
# ENUMS
# ============================

class UserRole(str, Enum):
    student = "student"
    advisor = "advisor"
    admin = "admin"

class UserStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    rejected = "rejected"


class CVStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    pending_advisor = "pending_advisor"
    approved = "approved"
    rejected = "rejected"


# ============================
# USERS
# ============================

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email ILIKE '%.cloud.neduet.edu.pk'",
            name="ck_users_email_university_domain"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    clerk_user_id = Column(String(255), unique=True, nullable=False, index=True)
    role = Column(SQLEnum(UserRole, name="user_role"), nullable=False)
    status = Column(
        SQLEnum(UserStatus, name="user_status"),
        default=UserStatus.active,
        nullable=False,
        index=True
    )
    department = Column(String(150), index=True, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    cvs = relationship("CVSubmission", back_populates="student")


# ============================
# CV SUBMISSIONS
# ============================

class CVSubmission(Base):
    __tablename__ = "cv_submissions"

    cv_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    student_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    status = Column(
        SQLEnum(CVStatus, name="cv_status"),
        default=CVStatus.draft,
        nullable=False,
        index=True
    )

    career_counseling = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    student = relationship("User", back_populates="cvs")

    personal_info = relationship("PersonalInfo", uselist=False, back_populates="cv", cascade="all, delete")
    academics = relationship("Academic", back_populates="cv", cascade="all, delete")
    internships = relationship("Internship", back_populates="cv", cascade="all, delete")
    industrial_visits = relationship("IndustrialVisit", back_populates="cv", cascade="all, delete")
    fyp = relationship("FYP", uselist=False, back_populates="cv", cascade="all, delete")
    certificates = relationship("Certificate", back_populates="cv", cascade="all, delete")
    achievements = relationship("Achievement", back_populates="cv", cascade="all, delete")
    skills = relationship("Skill", back_populates="cv", cascade="all, delete")
    extra_curricular = relationship("ExtraCurricular", back_populates="cv", cascade="all, delete")
    references = relationship("Reference", back_populates="cv", cascade="all, delete")


Index("idx_student_status", CVSubmission.student_id, CVSubmission.status)


# ============================
# PERSONAL INFO (1-to-1)
# ============================

class PersonalInfo(Base):
    __tablename__ = "personal_info"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    name = Column(String(150))
    father_name = Column(String(150))
    department = Column(String(150))
    batch = Column(String(4), index=True)
    cell = Column(String(11))
    roll_no = Column(String(8))
    cnic = Column(String(11))
    email = Column(String(150))
    gender = Column(String(20))
    dob = Column(Date)
    address = Column(Text)

    cv = relationship("CVSubmission", back_populates="personal_info")


# ============================
# ACADEMICS
# ============================

class Academic(Base):
    __tablename__ = "academics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    degree = Column(String(100))
    university = Column(String(150))
    year = Column(String(10))
    gpa = Column(String(20), index=True)
    majors = Column(String(150))

    cv = relationship("CVSubmission", back_populates="academics")


# ============================
# FYP (FINAL YEAR PROJECT)
# ============================

class FYP(Base):
    __tablename__ = "fyp"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    title = Column(String(200))
    company = Column(String(150), index=True)
    objectives = Column(Text)

    cv = relationship("CVSubmission", back_populates="fyp")


# ============================
# INTERNSHIPS
# ============================

class Internship(Base):
    __tablename__ = "internships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    organization = Column(String(150), index=True)
    position = Column(String(150))
    field = Column(String(150))
    from_date = Column(Date)
    to_date = Column(Date)

    cv = relationship("CVSubmission", back_populates="internships")


# ============================
# INDUSTRIAL VISITS
# ============================

class IndustrialVisit(Base):
    __tablename__ = "industrial_visits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    organization = Column(String(150))
    purpose = Column(Text)
    visit_date = Column(String(50))

    cv = relationship("CVSubmission", back_populates="industrial_visits")


# ============================
# CERTIFICATES
# ============================

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    name = Column(String(200))

    cv = relationship("CVSubmission", back_populates="certificates")


# ============================
# ACHIEVEMENTS
# ============================

class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    description = Column(String(300))

    cv = relationship("CVSubmission", back_populates="achievements")


# ============================
# SKILLS
# ============================

class Skill(Base):
    __tablename__ = "skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    name = Column(String(100), index=True)

    cv = relationship("CVSubmission", back_populates="skills")


# ============================
# EXTRA CURRICULAR
# ============================

class ExtraCurricular(Base):
    __tablename__ = "extra_curricular"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    activity = Column(String(200))

    cv = relationship("CVSubmission", back_populates="extra_curricular")


# ============================
# REFERENCES
# ============================

class Reference(Base):
    __tablename__ = "references"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cv_id = Column(UUID(as_uuid=True), ForeignKey("cv_submissions.cv_id", ondelete="CASCADE"))

    name = Column(String(150))
    contact = Column(String(100))
    occupation = Column(String(150))
    relation = Column(String(100))

    cv = relationship("CVSubmission", back_populates="references")