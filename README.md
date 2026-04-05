---
title: Moloj Bot
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 8080
---

# Moloj Discord Bot

This is the Hugging Face Space environment for the Moloj Discord Bot! 
The bot runs 24/7 inside the Docker container, reading from the `bot.py` script.

## Ping Server
The bot exposes an HTTP listener on port `8080` (mapped natively by Hugging Face via the `app_port: 8080` property) so that services like UptimeRobot can securely ping the container and keep the Space awake indefinitely.
