from typing import NamedTuple


class Base(NamedTuple):
    name: str
    version: str
    description: str | None
    url: str | None
    num_votes: int
    popularity: float
    maintainer: str | None
    submitter: str | None
    first_submitted: int
    last_modified: int
    out_of_date: int | None


class Package(NamedTuple):
    name: str
    base_name: str
    url_path: str


class Tracker(NamedTuple):
    base_name: str
    building: bool
    failed: bool
    build_version: str | None
