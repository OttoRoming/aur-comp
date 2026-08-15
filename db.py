import os
from typing import Tuple

import aiosqlite as sql

from common import ROOT_DIR
from models import Base, Package, Tracker

DATABASE_DIR = os.path.join(ROOT_DIR, "database")
DATABASE_PATH = os.path.join(DATABASE_DIR, "database.db")

db: sql.Connection


async def init() -> None:
    os.makedirs(DATABASE_DIR, exist_ok=True)

    global db
    db = await sql.connect(DATABASE_PATH)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS base (
            name TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            description TEXT,
            url TEXT,
            num_votes INTEGER NOT NULL,
            popularity REAL NOT NULL,
            maintainer TEXT,
            submitter TEXT,
            first_submitted INTEGER NOT NULL,
            last_modified INTEGER NOT NULL,
            out_of_date INTEGER
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS package (
            name TEXT PRIMARY KEY,
            base_name TEXT NOT NULL,
            url_path TEXT NOT NULL,
            FOREIGN KEY (base_name) REFERENCES base(name)
        );
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS tracker (
            base_name TEXT PRIMARY KEY,
            building INTEGER NOT NULL,
            failed INTEGER NOT NULL,
            build_version TEXT,
            FOREIGN KEY (base_name) REFERENCES base(name)
        );
    """)

    await db.commit()


async def commit():
    await db.commit()


async def add_package(base: Base, package: Package):
    await db.execute(
        """
        INSERT OR REPLACE INTO base (name, version, description, url, num_votes, popularity, maintainer, submitter, first_submitted, last_modified, out_of_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            base.name,
            base.version,
            base.description,
            base.url,
            base.num_votes,
            base.popularity,
            base.maintainer,
            base.submitter,
            base.first_submitted,
            base.last_modified,
            base.out_of_date,
        ),
    )

    await db.execute(
        """
        INSERT INTO package (name, base_name, url_path)
        VALUES (?, ?, ?)
    """,
        (package.name, package.base_name, package.url_path),
    )


async def get_package_count() -> int:
    async with db.execute("SELECT COUNT(*) FROM package") as cursor:
        row = await cursor.fetchone()
        return row[0] if row else 0


async def add_next_tracker() -> Tracker:
    async with db.execute(
        """
        SELECT b.name
        FROM base b
        LEFT JOIN tracker t ON b.name = t.base_name
        WHERE t.base_name IS NULL
        ORDER BY b.num_votes DESC, b.popularity DESC
        LIMIT 1
    """
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None, "No packages left to track"
    base_name = row[0]

    async with db.execute(
        """
        INSERT INTO tracker (base_name, building, failed, build_version)
        VALUES (?, 0, 0, NULL)
        RETURNING base_name, building, failed, build_version
    """,
        (base_name,),
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None, "Failed to insert new tracker"
    return Tracker(
        base_name=row[0],
        building=bool(row[1]),
        failed=bool(row[2]),
        build_version=row[3],
    )


async def get_next_unbuilt() -> Tuple[Tracker, Base]:
    while True:
        async with db.execute(
            """
            SELECT t.base_name, t.building, t.failed, t.build_version, b.name, b.version, b.description, b.url, b.num_votes, b.popularity, b.maintainer, b.submitter, b.first_submitted, b.last_modified, b.out_of_date
            FROM base b
            INNER JOIN tracker t ON b.name = t.base_name

            WHERE
            t.building = 0 AND
            t.failed = 0 AND
            t.build_version IS NULL AND
            b.out_of_date IS NULL AND
            b.num_votes > 100 AND
            b.name NOT LIKE '%-bin' AND
            b.name NOT LIKE '%-git'

            ORDER BY b.num_votes DESC, b.popularity DESC
            LIMIT 1
        """
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            try:
                await add_next_tracker()
            except AssertionError:
                raise RuntimeError("No unbuilt packages left to process")
            continue

        return (
            Tracker(
                base_name=row[0],
                building=bool(row[1]),
                failed=bool(row[2]),
                build_version=row[3],
            ),
            Base(
                name=row[4],
                version=row[5],
                description=row[6],
                url=row[7],
                num_votes=row[8],
                popularity=row[9],
                maintainer=row[10],
                submitter=row[11],
                first_submitted=row[12],
                last_modified=row[13],
                out_of_date=row[14],
            ),
        )


async def get_packages_from_base_name(base_name: str) -> list[Package]:
    async with db.execute(
        """
        SELECT name, base_name, url_path
        FROM package
        WHERE base_name = ?
    """,
        (base_name,),
    ) as cursor:
        rows = await cursor.fetchall()
    return [Package(name=row[0], base_name=row[1], url_path=row[2]) for row in rows]


async def update_tracker(tracker: Tracker):
    await db.execute(
        """
        UPDATE tracker
        SET building = ?, failed = ?, build_version = ?
        WHERE base_name = ?
    """,
        (
            int(tracker.building),
            int(tracker.failed),
            tracker.build_version,
            tracker.base_name,
        ),
    )


async def get_packages_building() -> list[Package]:
    async with db.execute(
        """
        SELECT p.name, p.base_name, p.url_path
        FROM package p
        INNER JOIN tracker t ON p.base_name = t.base_name
        WHERE t.building = 1
    """
    ) as cursor:
        rows = await cursor.fetchall()
    return [Package(name=row[0], base_name=row[1], url_path=row[2]) for row in rows]


async def get_packages_built() -> list[Package]:
    async with db.execute(
        """
        SELECT p.name, p.base_name, p.url_path
        FROM package p
        INNER JOIN tracker t ON p.base_name = t.base_name
        WHERE t.building = 0 AND t.failed = 0 AND t.build_version IS NOT NULL
    """
    ) as cursor:
        rows = await cursor.fetchall()
    return [Package(name=row[0], base_name=row[1], url_path=row[2]) for row in rows]


async def get_packages_failed() -> list[Package]:
    async with db.execute(
        """
        SELECT p.name, p.base_name, p.url_path
        FROM package p
        INNER JOIN tracker t ON p.base_name = t.base_name
        WHERE t.building = 0 AND t.failed = 1
    """
    ) as cursor:
        rows = await cursor.fetchall()
    return [Package(name=row[0], base_name=row[1], url_path=row[2]) for row in rows]
