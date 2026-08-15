import asyncio
import os
import shutil
import sys
from typing import Literal

import paramiko
from aiofiles import os as aos

import db
from common import ROOT_DIR
from models import Base

WORK_DIR = os.path.join(ROOT_DIR, "work")
SOURCES_DIR = os.path.join(WORK_DIR, "sources")
BUILD_DIR = os.path.join(WORK_DIR, "build")
BIN_DIR = os.path.join(ROOT_DIR, "bin")


async def subprocess(args: list[str], cwd: str | None = None) -> None:
    if cwd is None:
        cwd = os.getcwd()

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    for line in stdout.decode().splitlines():
        print(f"[stdout] {line}")
    for line in stderr.decode().splitlines():
        print(f"[stderr] {line}")

async def setup() -> None:
    # delete everything in WORK_DIR
    if await aos.path.exists(WORK_DIR):
        for item in await aos.listdir(WORK_DIR):
            item_path = os.path.join(WORK_DIR, item)
            if await aos.path.isdir(item_path):
                await asyncio.to_thread(shutil.rmtree, item_path)
            else:
                await aos.remove(item_path)

    await aos.makedirs(SOURCES_DIR, mode=0o777, exist_ok=True)
    await aos.makedirs(BUILD_DIR, mode=0o777, exist_ok=True)

    await aos.makedirs(BIN_DIR, mode=0o777, exist_ok=True)


async def fetch_base(name: str) -> None:
    package_dir = os.path.join(SOURCES_DIR, name)
    await aos.makedirs(package_dir, exist_ok=True)

    if await aos.path.exists(os.path.join(package_dir, ".git")):
        await subprocess(["git", "pull"], cwd=package_dir)
    else:
        git_url = f"https://aur.archlinux.org/{name}.git"
        await subprocess(["git", "clone", git_url, package_dir])
        os.chmod(package_dir, 0o777)


async def build_base(base: Base) -> None:
    await fetch_base(base.name)

    build_base_dir = os.path.join(BUILD_DIR, base.name)
    source_base_dir = os.path.join(SOURCES_DIR, base.name)

    await asyncio.to_thread(shutil.rmtree, build_base_dir, True)

    _ = await asyncio.to_thread(
        shutil.copytree,
        source_base_dir,
        build_base_dir,
    )

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname="builder", username="builder", password="password", timeout=60)

    transport = ssh.get_transport()
    assert transport is not None

    channel = transport.open_session()

    remove_orphans = "sudo pacman -Rns $(pacman -Qtdq) --noconfirm || true"
    command = f"""
        {remove_orphans} &&

        cd ~/work/build/{base.name} &&

        source PKGBUILD &&
        if [ ! -z "${{validpgpkeys}}" ]; then
            gpg --recv-keys ${{validpgpkeys}}
        fi &&

        makepkg -s --noconfirm &&

        {remove_orphans}
    """

    channel.exec_command(command)

    while True:
        if channel.recv_ready():
            data = channel.recv(1024).decode("utf-8", errors="ignore")
            _ = sys.stdout.write(data)
            _ = sys.stdout.flush()

        if channel.recv_stderr_ready():
            err_data = channel.recv_stderr(1024).decode("utf-8", errors="ignore")
            _ = sys.stderr.write(err_data)
            _ = sys.stderr.flush()

        if (
            channel.exit_status_ready()
            and not channel.recv_ready()
            and not channel.recv_stderr_ready()
        ):
            break

        await asyncio.sleep(0.01)

    packages = await db.get_packages_from_base_name(base.name)
    for package in packages:
        arch: Literal["x86_64", "any"]

        extension = ".pkg.tar.lz"

        if await aos.path.exists(
            os.path.join(
                build_base_dir, f"{package.name}-{base.version}-x86_64{extension}"
            )
        ):
            arch = "x86_64"
        elif await aos.path.exists(
            os.path.join(
                build_base_dir, f"{package.name}-{base.version}-any{extension}"
            )
        ):
            arch = "any"
        else:
            raise Exception(f"Package {package.name} not found in build directory")

        _ = await asyncio.to_thread(
            shutil.move,
            os.path.join(
                build_base_dir, f"{package.name}-{base.version}-{arch}{extension}"
            ),
            os.path.join(BIN_DIR, f"{package.name}-{base.version}-{arch}{extension}"),
        )
