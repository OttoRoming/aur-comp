# AUR Comp

podman build --cgroup-manager=cgroupfs -t aur-comp .
docker run --rm -p 8000:8000 your-image-name
