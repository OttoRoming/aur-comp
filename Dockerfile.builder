FROM archlinux:base-devel

RUN pacman -Syu --noconfirm

RUN pacman-key --init

RUN pacman -S --noconfirm --needed \
    archlinux-keyring \
    sudo \
    git \
    lzip \
    openssh

RUN pacman-db-upgrade
RUN update-ca-trust

RUN pacman -Scc --noconfirm

RUN echo '%wheel ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/wheel-nopasswd
RUN chmod 0440 /etc/sudoers.d/wheel-nopasswd

RUN sed -i \
  's/^COMPRESSLZ=(lzip -c -f)$/COMPRESSLZ=(lzip -c -f -9)/' \
  /etc/makepkg.conf
RUN sed -i \
  "s/^PKGEXT='\.pkg\.tar\.zst'\$/PKGEXT='\.pkg\.tar\.lz'/" \
  /etc/makepkg.conf
RUN echo 'MAKEFLAGS="-j32"' >> /etc/makepkg.conf

RUN useradd -m -G wheel builder
RUN printf 'password\npassword\n' | passwd builder

RUN ssh-keygen -A
RUN mkdir -p /var/run/sshd
