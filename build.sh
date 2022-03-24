#!/bin/bash
docker buildx build --platform linux/arm64,linux/amd64 --push -t reg.thecovrigs.net/acovrig/sgsda-discord:latest -f Dockerfile-alpine .
rsync -avhrP --exclude __pycache__ --delete-before ./ acovrig@192.168.5.76:/mnt/user/projects/church/sgsda_discord/