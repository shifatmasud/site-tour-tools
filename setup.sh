#!/usr/bin/env bash
# Site Tour dependencies for an Ubuntu/Debian VM with no GPU.
# Installs: Xvfb (virtual display), ffmpeg (capture + encode), Playwright + its Chromium, Pillow (frame checks).
set -e
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"
$SUDO apt-get update -y
$SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y xvfb ffmpeg fonts-noto-color-emoji fonts-liberation
python3 -m pip install --upgrade playwright pillow 2>/dev/null || python3 -m pip install --break-system-packages --upgrade playwright pillow
python3 -m playwright install --with-deps chromium
echo "Site Tour ready: python3 site_tour.py https://example.com --probe"
