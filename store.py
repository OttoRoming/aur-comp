import copy
import gzip
import json
import os
import shutil
import threading
from datetime import datetime

import requests

from common import ROOT_DIR, PackageInfo

WORK_DIR = os.path.join(ROOT_DIR, "store")
STORE_FILE = os.path.join(WORK_DIR, "store.json")
STORE_FILE_BACKUP = os.path.join(WORK_DIR, "store.json.backup")

PACKAGES_ARCHIVE = "packages-meta-v1.json.gz"
PACKAGES_URL = f"https://aur.archlinux.org/{PACKAGES_ARCHIVE}"
PACKAGES_SHA256_URL = f"{PACKAGES_URL}.sha256"


class Store:
    def __init__(self) -> None:
        if os.path.exists(STORE_FILE):
            with open(STORE_FILE, "r") as f:
                self.deserialize(f.read())
        else:
            self.lock = threading.Lock()
            self.fetch_packages()
            self.packages_built: set[int] = set()
            self.packages_building: set[int] = set()
            self.known_bad_packages: set[int] = set()

    def is_stale(self) -> bool:
        with self.lock:
            if self.last_updated is None:
                return True

            return (datetime.now() - self.last_updated).total_seconds() > 3600

    def fetch_packages(self) -> None:
        response = requests.get(PACKAGES_URL)
        data = json.loads(gzip.decompress(response.content))
        with self.lock:
            self.last_updated = datetime.now()
            self.packages = data
            self.packages.sort(key=lambda p: p["NumVotes"], reverse=True)

    def save(self) -> None:
        os.makedirs(WORK_DIR, exist_ok=True)

        if os.path.exists(STORE_FILE):
            shutil.move(STORE_FILE, STORE_FILE_BACKUP)

        with open(STORE_FILE, "w") as f:
            f.write(self.serialize())

    def get_packages(self) -> list[PackageInfo]:
        with self.lock:
            return copy.deepcopy(self.packages)

    def get_packages_built(self) -> set[int]:
        with self.lock:
            return copy.deepcopy(self.packages_built)

    def get_packages_building(self) -> set[int]:
        with self.lock:
            return copy.deepcopy(self.packages_building)

    def get_known_bad_packages(self) -> set[int]:
        with self.lock:
            return copy.deepcopy(self.known_bad_packages)

    def get_next_package_to_build(self) -> PackageInfo:
        packages = self.get_packages()
        packages_built = self.get_packages_built()
        packages_building = self.get_packages_building()
        known_bad_packages = self.get_known_bad_packages()

        for package in packages:
            if (
                package["ID"] not in packages_built
                and package["ID"] not in packages_building
                and package["ID"] not in known_bad_packages
                and package["Name"] == package["PackageBase"]
                and not package["Name"].endswith("-git")
                and not package["Name"].endswith("-bin")
            ):
                return package

        raise Exception("No packages left to build")

    def get_shared_base(self, package_id: int) -> set[int]:
        packages = self.get_packages()
        shared_base: set[int] = set()
        base_name = ""

        for package in packages:
            if package["ID"] == package_id:
                base_name = package["PackageBase"]
                break

        for package in packages:
            if package["PackageBase"] == base_name:
                shared_base.add(package["ID"])

        return shared_base

    def serialize(self) -> str:
        with self.lock:
            return json.dumps(
                {
                    "packages_built": list(self.packages_built),
                    "packages_building": list(self.packages_building),
                    "known_bad_packages": list(self.known_bad_packages),
                }
            )

    def deserialize(self, data: str) -> None:
        self.lock = threading.Lock()
        self.fetch_packages()
        state = json.loads(data)
        with self.lock:
            self.packages_built = set(state["packages_built"])
            self.packages_building = set(state["packages_building"])
            self.known_bad_packages = set(state["known_bad_packages"])


store = Store()
