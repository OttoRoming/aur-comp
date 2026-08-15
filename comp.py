import os
import shutil
import subprocess
import sys
import time

import paramiko

from common import ROOT_DIR, PackageInfo

WORK_DIR = os.path.join(ROOT_DIR, "work")
SOURCES_DIR = os.path.join(WORK_DIR, "sources")
BUILD_DIR = os.path.join(WORK_DIR, "build")
BIN_DIR = os.path.join(ROOT_DIR, "bin")


def setup() -> None:
    # delete everything in WORK_DIR
    if os.path.exists(WORK_DIR):
        for item in os.listdir(WORK_DIR):
            item_path = os.path.join(WORK_DIR, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)

    os.makedirs(SOURCES_DIR, mode=0o777)
    os.makedirs(BUILD_DIR, mode=0o777)

    os.makedirs(BIN_DIR, mode=0o777, exist_ok=True)


def fetch_package(package: PackageInfo) -> None:
    package_dir = os.path.join(SOURCES_DIR, package["PackageBase"])
    os.makedirs(package_dir, exist_ok=True)

    if os.path.exists(os.path.join(package_dir, ".git")):
        subprocess.run(["git", "pull"], cwd=package_dir, check=True)
    else:
        git_url = f"https://aur.archlinux.org/{package['PackageBase']}.git"
        subprocess.run(["git", "clone", git_url, package_dir], check=True)
        os.chmod(package_dir, 0o777)


def build_package(package: PackageInfo) -> None:
    fetch_package(package)

    build_base_dir = os.path.join(BUILD_DIR, package["PackageBase"])
    source_base_dir = os.path.join(SOURCES_DIR, package["PackageBase"])

    shutil.rmtree(build_base_dir, ignore_errors=True)

    shutil.copytree(
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

        cd ~/work/build/{package["PackageBase"]} &&

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
            sys.stdout.write(data)
            sys.stdout.flush()

        if channel.recv_stderr_ready():
            err_data = channel.recv_stderr(1024).decode("utf-8", errors="ignore")
            sys.stderr.write(err_data)
            sys.stderr.flush()

        if (
            channel.exit_status_ready()
            and not channel.recv_ready()
            and not channel.recv_stderr_ready()
        ):
            break

        time.sleep(0.01)

    filename = f"{package['PackageBase']}-{package['Version']}-x86_64.pkg.tar.lz"
    shutil.move(
        os.path.join(build_base_dir, filename),
        os.path.join(BIN_DIR, filename),
    )
