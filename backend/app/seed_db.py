import asyncio
import random
from faker import Faker

import database
from models import (
    User, UserRole, UserStatus,
    CVSubmission, CVStatus,
    PersonalInfo, Academic, Skill,
    Internship, Achievement
)

fake = Faker()


async def seed_users(session):
    users = []

    # Admin
    admin = User(
        email="admin@cloud.neduet.edu.pk",
        clerk_user_id="admin_dev",
        role=UserRole.admin,
        status=UserStatus.active
    )
    users.append(admin)

    # Advisors
    for i in range(2):
        advisor = User(
            email=f"advisor{i}@cloud.neduet.edu.pk",
            clerk_user_id=f"advisor_dev_{i}",
            role=UserRole.advisor,
            status=UserStatus.active
        )
        users.append(advisor)

    # Students
    for i in range(10):
        student = User(
            email=f"student{i}@cloud.neduet.edu.pk",
            clerk_user_id=f"student_dev_{i}",
            role=UserRole.student,
            status=UserStatus.active
        )
        users.append(student)

    session.add_all(users)
    await session.commit()

    return users


async def seed_cvs(session, students):
    cvs = []

    for student in students:
        if student.role != UserRole.student:
            continue

        cv = CVSubmission(
            student_id=student.id,
            status=random.choice(list(CVStatus))
        )

        session.add(cv)
        await session.flush()

        # Personal info
        p = PersonalInfo(
            cv_id=cv.cv_id,
            name=fake.name(),
            father_name=fake.name(),
            department="Software Engineering",
            batch="2024",
            cell="03123456789",
            roll_no=str(random.randint(10000000, 99999999)),
            cnic="4210112345671",
            email=student.email,
            gender="Male",
            address=fake.address()
        )
        session.add(p)

        # Academics
        for _ in range(2):
            a = Academic(
                cv_id=cv.cv_id,
                degree="BS Software Engineering",
                university="NED University",
                year=str(random.randint(2020, 2024)),
                gpa=str(round(random.uniform(2.5, 3.8), 2)),
                majors="Computer Science"
            )
            session.add(a)

        # Skills
        skills = ["Python", "Go", "Docker", "Kubernetes", "AWS"]
        for s in random.sample(skills, 3):
            skill = Skill(
                cv_id=cv.cv_id,
                name=s
            )
            session.add(skill)

        # Internship
        internship = Internship(
            cv_id=cv.cv_id,
            organization=fake.company(),
            position="Software Intern",
            field="Backend",
            from_date=fake.date_between("-2y"),
            to_date=fake.date_between("-1y")
        )
        session.add(internship)

        # Achievement
        achievement = Achievement(
            cv_id=cv.cv_id,
            description="Winner of university hackathon"
        )
        session.add(achievement)

        cvs.append(cv)

    await session.commit()

    return cvs


async def main():
    database.init_db()

    async with database.AsyncSessionLocal() as session:
        students = await seed_users(session)
        await seed_cvs(session, students)

    print("Database seeded successfully 🚀")


if __name__ == "__main__":
    asyncio.run(main())