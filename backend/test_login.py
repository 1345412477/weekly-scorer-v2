import asyncio
from app.database import async_session
from app.models.models import Person
from sqlalchemy import select

async def main():
    async with async_session() as db:
        result = await db.execute(select(Person).where(Person.name == "admin").limit(1))
        admin = result.scalar_one_or_none()
        if admin:
            print(f"admin found: id={admin.id}, role={getattr(admin, 'role', 'N/A')}")
            # Check if there's a password field
            for col in admin.__table__.columns:
                print(f"  {col.name}: {getattr(admin, col.name, 'N/A')}")
        else:
            print("admin not found in persons table")
            
        # Check all persons with role
        result2 = await db.execute(select(Person))
        for p in result2.scalars().all():
            role = getattr(p, 'role', 'N/A')
            print(f"Person: {p.name}, role={role}")

asyncio.run(main())
