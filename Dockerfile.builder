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


RUN useradd -m -G wheel builder
RUN printf 'password\npassword\n' | passwd builder

# Install plzip
RUN git clone https://aur.archlinux.org/plzip.git /home/builder/plzip
RUN chown -R builder:builder /home/builder/plzip
RUN sudo -u builder bash -c 'cd /home/builder/plzip && makepkg -si --noconfirm --skippgpcheck'

# Configure makepkg to user plzip
RUN sed -i \
  's/^COMPRESSLZ=(lzip -c -f)$/COMPRESSLZ=(plzip -c -f -9 -n 32)/' \
  /etc/makepkg.conf && \
  sed -i \
  "s/^PKGEXT='\.pkg\.tar\.zst'\$/PKGEXT='\.pkg\.tar\.lz'/" \
  /etc/makepkg.conf

RUN echo 'MAKEFLAGS="-j32"' >> /etc/makepkg.conf

RUN ssh-keygen -A
RUN mkdir -p /var/run/sshd
