# AfterlifeOS Build System 🚀

![Build Status](https://img.shields.io/github/actions/workflow/status/AfterlifeOS/AfterlifeOS-Builder/build.yml?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green.svg?style=for-the-badge)
![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Linux-orange.svg?style=for-the-badge&logo=linux&logoColor=white)

An automated **CI/CD pipeline** designed for building **AfterlifeOS** (and other Android ROMs), fully integrated with a **Telegram Bot** for remote management, monitoring, and release distribution.

## 📋 Table of Contents
- [✨ Key Features](#-key-features)
- [🎯 Project Goal](#-project-goal)
- [📂 Project Structure](#-project-structure)
- [🛠️ Installation & Setup](#%EF%B8%8F-installation--setup)
- [🤖 Usage](#-usage)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## ✨ Key Features

*   **🤖 Telegram Bot Integration:** Control your build infrastructure from anywhere using simple commands.
*   **🏗 Remote Build Triggering:** Launch GitHub Actions workflows to build ROMs for specific devices (`/build`).
*   **👥 User Management:** Role-based access control (User, Admin, Owner) with whitelist support.
*   **⏳ Quota System:** Enforced daily build limits per user to manage resources efficiently.
*   **📢 OTA & Release Management:** Generate and publish formatted ROM release posts with banners and changelogs (`/post`).
*   **📊 Real-time Status:** Get live updates on build progress and success/failure notifications.
*   **🧹 Smart Cleanup:** Intelligent logic to manage disk space between builds.

---

## 🎯 Project Goal

The primary goal of this project is to democratize and streamline the Android ROM compilation process. By bridging the gap between complex CI/CD infrastructure (GitHub Actions) and a user-friendly interface (Telegram), we aim to:

1.  **Reduce Friction:** Eliminate the need for constant terminal monitoring and manual server management.
2.  **Enhance Accessibility:** Allow developers to trigger and monitor builds from mobile devices.
3.  **Ensure Stability:** Enforce resource quotas and automated cleanups to maintain a healthy build environment.

---

## 📂 Project Structure

```text
/
├── .github/
│   └── workflows/
│       └── build.yml          # GitHub Actions CI workflow definition
├── builder/                   # Core build scripts & logic
│   ├── utils/
│   │   └── telegram.py        # Telegram notification utility for builder
│   ├── build.sh               # Main Android build script (lunch & make)
│   ├── fsgen_control.sh       # Controls filesystem generation options
│   ├── gms_variant_control.sh # Manages GMS variants (Core, Basic, etc.)
│   ├── quota_manager.py       # Manages user quotas & database updates
│   ├── reporter.py            # Reports build status/results
│   └── sync.sh                # Repo sync script
├── telegram-bot/              # Telegram Bot source code
│   ├── handlers/              # Command handlers
│   │   ├── admin.py           # Admin commands (adduser, setbanner, etc.)
│   │   ├── general.py         # General commands (start, help, listuser)
│   │   ├── github.py          # GitHub interaction (build, status, cancel)
│   │   └── ota.py             # OTA Release management (post, banner)
│   ├── main.py                # Bot entry point and startup logic
│   ├── requirements.txt       # Python dependencies for the bot
│   └── utils.py               # Shared utility functions (formatting, redis)
├── database.json              # User database (roles, quotas, history)
└── README.md                  # Project documentation
```

---

## 🛠️ Installation & Setup

### Prerequisites

*   **Python 3.8+**
*   **Redis Server** (for state management)
*   **GitHub Account** (for hosting the repo & running Actions)
*   **Telegram Bot Token** (from @BotFather)

### Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/your-username/afterlife-build-system.git
    cd afterlife-build-system
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r telegram-bot/requirements.txt
    ```

3.  **Configuration**
    Set up your environment variables (e.g., in a `.env` file or system env):
    *   `BOT_TOKEN`: Your Telegram Bot API Token.
    *   `REDIS_URL`: Connection string for Redis.
    *   `GITHUB_TOKEN`: Personal Access Token (PAT) with repo scope.
    *   `GITHUB_REPO_NAME`: `username/repo`.
    *   `TELEGRAM_CHAT_ID`: Admin/Log chat ID.
    *   `OWNER_ID`: Telegram ID of the bot owner.

4.  **Run the Bot**
    ```bash
    python telegram-bot/main.py
    ```

---

## 🤖 Usage

### 👤 User Commands
| Command | Description |
| :--- | :--- |
| `/start` | Check if the bot is online. |
| `/help` | Show available commands based on your role. |
| `/build <device>` | Trigger a new build (e.g., `/build citrus`). |
| `/status` | Check the status of running builds. |
| `/quota` | View your remaining daily build quota. |
| `/cancel <RunID>` | Cancel your own running build. |
| `/post <device>` | Create a release post for a device (needs banner set). |
| `/banner` | View the current OTA release banner. |
| `/listuser` | List all registered users and their roles. |

### 🛡️ Admin Commands
*Accessible to Admins and Owner.*

| Command | Description |
| :--- | :--- |
| `/adduser <id> <name> [role]` | Whitelist a new user or update existing one. |
| `/removeuser <id>` | Remove a user from the database. |
| `/setbanner` | Set the OTA release banner (Reply to an image). |
| `/removebanner` | Remove the current OTA banner. |
| **Note** | Admins have unlimited build quota and can cancel *any* build. |

### 👑 Owner Commands
*Exclusive to the Bot Owner.*

| Command | Description |
| :--- | :--- |
| `/setrole <id> <role>` | Promote/Demote users (Roles: `user`, `admin`). |
| `/addquota <user> <amt>` | Manually add extra quota to a user for the day. |

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.

```text
MIT License

Copyright (c) 2025 AfterlifeOS

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

<br>
<p align="center">
  Built with ❤️ by the <a href="https://github.com/AfterlifeOS">AfterlifeOS Team</a>
</p>
