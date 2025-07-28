🧠 DOS & TISRouter Management App

A lightweight full-stack application built with **Flask** and **SQLite**, designed to streamline configuration and deployment of **TISRouter IP setups** and **Data Output Sheets (DOS)**. Perfect for managing IP-based controller networks (e.g., Teletrol) and exporting configuration files for system integration.

---

🚀 Features

- 🏗 Add/remove/restore **building network entries** with IP validation
- 📥 Export:
  - ✅ Master IP list (`TNR_x` format)
  - ✅ Individual INI files for each building
  - ✅ A full ZIP of all INI configurations
  - ✅ Windows XP `ROUTERS` config file
- 📊 Timestamped action logging (`added`, `removed`, `reactivated`)
- 🧠 Smart duplicate detection and IP conflict resolution
- 💾 Backed by **SQLite** and autoseeded on first launch
- 🌐 Auto-opens local web UI via **Flask**
