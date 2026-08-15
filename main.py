#!/usr/bin/env python3

import asyncio
import copy
import gzip
import json
from pathlib import Path

import httpx
from quart import Quart

import comp
import db
from models import Base, Package

BASE_DIR = Path(__file__).parent
PACKAGES_ARCHIVE = "packages-meta-v1.json.gz"
PACKAGES_URL = f"https://aur.archlinux.org/{PACKAGES_ARCHIVE}"

app = Quart(__name__)


@app.route("/")
async def index() -> str:
    package_count = await db.get_package_count()
    building = await db.get_packages_building()
    built = await db.get_packages_built()
    failed = await db.get_packages_failed()

    return f"""
        <h1>AUR Comp</h1>
        <h2>Package Count: {package_count}</h2>
        <h3>Building:</h3>
        <ul>
            {"".join(f"<li>{pkg.name} ({pkg.base_name})</li>" for pkg in building)}
        </ul>
        <h3>Built:</h3>
        <ul>
            {"".join(f"<li>{pkg.name} ({pkg.base_name})</li>" for pkg in built)}
        </ul>
        <h3>Failed:</h3>
        <ul>
            {"".join(f"<li>{pkg.name} ({pkg.base_name})</li>" for pkg in failed)}
        </ul>
    """


async def fetch_packages() -> None:
    async with httpx.AsyncClient() as client:
        response = await client.get(PACKAGES_URL)

    response.raise_for_status()
    data = json.loads(gzip.decompress(response.content))

    for package in data:
        base = Base(
            name=package["PackageBase"],
            version=package["Version"],
            description=package["Description"],
            url=package["URL"],
            num_votes=package["NumVotes"],
            popularity=package["Popularity"],
            maintainer=package["Maintainer"],
            submitter=package["Submitter"],
            first_submitted=package["FirstSubmitted"],
            last_modified=package["LastModified"],
            out_of_date=package.get("OutOfDate"),
        )

        package = Package(
            name=package["Name"],
            base_name=package["PackageBase"],
            url_path=package["URLPath"],
        )

        await db.add_package(base, package)

    await db.commit()


async def main_loop() -> None:
    while True:
        tracker, base = await db.get_next_unbuilt()
        tracker = copy.replace(tracker, building=True)
        await db.update_tracker(tracker)
        await db.commit()

        try:
            await comp.build_base(base)
        except Exception as e:
            print(f"Error building base {base.name}: {e}")
            tracker = copy.replace(tracker, building=False, failed=True)
            await db.update_tracker(tracker)
            await db.commit()
            continue

        tracker = copy.replace(
            tracker, building=False, failed=False, build_version=base.version
        )
        await db.update_tracker(tracker)
        await db.commit()


async def main() -> None:
    await db.init()
    await db.clear_building_flags()
    await db.commit()

    package_count = await db.get_package_count()
    if package_count == 0:
        print("Fetching packages from AUR...")
        await fetch_packages()
        package_count = await db.get_package_count()

    print(f"{package_count} packages in database")

    await asyncio.gather(main_loop(), app.run_task(host="0.0.0.0", port=80))


if __name__ == "__main__":
    asyncio.run(main())
