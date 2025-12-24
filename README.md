# AfterlifeOS Build System 🚀

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Android%20%7C%20Linux-orange.svg)

An automated **CI/CD pipeline** designed for building **AfterlifeOS** (and other Android ROMs), fully integrated with a **Telegram Bot** for remote management, monitoring, and release distribution.

This project streamlines the development workflow by allowing maintainers to trigger builds, check quotas, and publish OTA updates directly from Telegram.

---

## ✨ Main Features

*   **🤖 Telegram Bot Integration:** Control your build infrastructure from anywhere using simple commands.
*   **🏗 Remote Build Triggering:** Launch GitHub Actions workflows to build ROMs for specific devices (`/build`).
*   **👥 User Management:** Role-based access control (User, Admin, Owner) with whitelist support.
*   **⏳ Quota System:** Enforced daily build limits per user to manage resources efficiently.
*   **📢 OTA & Release Management:** Generate and publish formatted ROM release posts with banners and changelogs (`/post`).
*   **📊 Real-time Status:** Get live updates on build progress and success/failure notifications.
*   **🧹 Smart Cleanup:** Intelligent logic to manage disk space between builds.

---

## 📂 Project Structure

```text
/
├── .github/workflows/   # GitHub Actions CI configurations
├── builder/             # Core build scripts & logic
│   ├── build.sh         # Main Android build script (lunch & make)
│   ├── quota_manager.py # Manages user quotas & database updates
│   └── ...
├── telegram-bot/        # Telegram Bot source code
│   ├── handlers/        # Command handlers (Admin, GitHub, OTA)
│   ├── main.py          # Bot entry point
│   └── requirements.txt # Python dependencies
└── database.json        # User database (roles, quotas, history)
```

---

## 🚀 Getting Started

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

4.  **Run the Bot**
    ```bash
    python telegram-bot/main.py
    ```

---

## 🎮 Usage

### User Commands
| Command | Description |
| :--- | :--- |
| `/start` | Check if the bot is online. |
| `/help` | Show available commands. |
| `/build <device> <type>` | Trigger a new build (e.g., `/build citrus userdebug`). |
| `/status` | Check the status of running builds. |
| `/quota` | View your remaining daily build quota. |
| `/cancel` | Cancel your currently running build. |

### Admin Commands
| Command | Description |
| :--- | :--- |
| `/adduser <id>` | Whitelist a new user. |
| `/removeuser <id>` | Remove a user. |
| `/setrole <id> <role>` | Set role (`user`, `admin`). |
| `/addquota <id>` | Manually increase a user's quota. |
| `/post <device>` | Create a release post for a device. |
| `/setbanner` | Set the OTA release banner (reply to an image). |

---

## 🤝 Contribution

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
