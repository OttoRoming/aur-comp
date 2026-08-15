import os
from typing import TypedDict

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


class PackageInfo(TypedDict):
    ID: int
    Name: str
    PackageBaseID: int
    PackageBase: str
    Version: str
    Description: str
    URL: str
    NumVotes: int
    Popularity: float
    OutOfDate: str | None
    Maintainer: str
    Submitter: str
    FirstSubmitted: int
    LastModified: int
    URLPath: str
