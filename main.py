#!/usr/bin/env python3

import threading

from flask import Flask

import comp
from store import store

app = Flask(__name__)


@app.route("/")
def index() -> str:
    packages = store.get_packages()
    building = store.get_packages_building()
    built = store.get_packages_built()
    failed = store.get_known_bad_packages()

    built_names = [p["Name"] for p in packages if p["ID"] in built]
    building_names = [p["Name"] for p in packages if p["ID"] in building]
    failed_names = [p["Name"] for p in packages if p["ID"] in failed]

    return (
        f"<h1>Built Packages</h1><ul>{''.join(f'<li>{name}</li>' for name in built_names)}</ul>"
        f"<h1>Building Packages</h1><ul>{''.join(f'<li>{name}</li>' for name in building_names)}</ul>"
        f"<h1>Failed Packages</h1><ul>{''.join(f'<li>{name}</li>' for name in failed_names)}</ul>"
    )


def main() -> None:
    # Start the Flask app in a separate thread
    threading.Thread(
        target=app.run,
        kwargs={"host": "0.0.0.0", "port": 80, "use_reloader": False},
        # daemon=True,
    ).start()

    comp.setup()

    while True:
        if store.is_stale():
            store.fetch_packages()

        package = store.get_next_package_to_build()
        related_packages = store.get_shared_base(package["ID"])
        with store.lock:
            store.packages_building.update(related_packages)

        try:
            comp.build_package(package)
        except Exception as e:
            print(f"Error building package {package['Name']}: {e}")
            with store.lock:
                store.packages_building.difference_update(related_packages)
                store.known_bad_packages.update(related_packages)
                continue

        with store.lock:
            store.packages_building.difference_update(related_packages)
            store.packages_built.update(related_packages)

        store.save()


if __name__ == "__main__":
    # while True:
    #     pass
    main()
