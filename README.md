# 🏢 Legacy Building Config Generator – TSIRouter & XP Tool

A local Flask-based configuration tool for managing **building controller IP assignments** and generating router configuration files compatible with **TSIRouter systems** used in **legacy Windows XP / DOS environments**.

---

## 🎯 Purpose

This tool streamlines the setup of building network definitions for TSIRouter deployments by:

- Auto-generating `.ini` and `ROUTERS` config files
- Ensuring valid and non-conflicting IP assignments
- Supporting easy building additions/removals with an interactive UI

---

## ✨ Features

- 🏗 Add, remove, and restore building numbers with associated IPs
- ✅ Validates IPs 
- 🧾 Export options:
  - `Master List` (`TNR_` format)
  - `Single INI` (excludes one building)
  - `All INIs` as a `.zip`
  - Windows XP `ROUTERS` config for TSIRouter
- 💽 SQLite database auto-seeded on first run
- 🧠 Action logging with timestamps (`added`, `removed`, `reactivated`)
- 🌐 Runs as a web app via Flask and auto-launches in browser
