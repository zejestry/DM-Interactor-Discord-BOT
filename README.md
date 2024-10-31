# Discord DM Interactor Bot

A powerful Discord bot that allows server administrators to securely interact with users through direct messages while maintaining full logging and control capabilities.

![Discord Bot](https://img.shields.io/badge/Discord-Bot-7289DA?style=for-the-badge&logo=discord&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)

## 📽️ Video

https://github.com/user-attachments/assets/4d2de92b-f684-4a7d-895c-0d978abb3722

## 🌟 Features

- **Secure DM Interaction**: Administrators can communicate with users through the bot
- **Message Logging**: Complete logging of all interactions
- **File Support**: Send and receive files with configurable restrictions
- **Reaction Mirroring**: Reactions are mirrored between admin and user messages
- **Advanced Commands**: Various utility commands for server management
- **Customizable**: Configurable prefix and settings
- **Backup System**: Built-in backup functionality for logs and configurations

## 📋 Requirements

- Python 3.8+
- discord.py
- psutil
- Other dependencies listed in requirements.txt

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/zejestry/DM-Interactor-Discord-BOT.git
cd DM-Interactor-Discord-BOT
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Configure the bot:
- Rename `config.example.json` to `config.json`
- Update the configuration with your preferences
- Replace the bot token in the code with your own Discord bot token

4. Run the bot:
```bash
python DM Interactor BOT.py
```

## ⚙️ Configuration

The `config.json` file contains important settings:

```json
{
    "prefix": "!",
    "default_logging": true,
    "max_file_size": 8388608,
    "allowed_file_types": [
        ".txt",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".mp4",
        ".pdf",
        ".zip",
        ".docx",
        ".xlsx"
    ]
}
```

## 💻 Commands

### Basic Commands
- `!helpme [command]` - Show help for all or specific command
- `!panel` - Show command panel
- `!startmsg <user_id>` - Start a DM session
- `!stopmsg` - Stop active DM session
- `!export` - Export chat logs
- `!prefix <new_prefix>` - Change command prefix

### Utility Commands
- `!status` - Show bot and system status
- `!ping` - Check bot latency
- `!userinfo [user_id]` - Get user information
- `!clear <amount>` - Clear messages
- `!backup` - Create config and logs backup

## 🔒 Security Features

- Admin-only access
- Configurable file type restrictions
- Size limits on file transfers
- Complete logging of all interactions
- Session management and timeout features

## 📝 Usage Example

1. Start a DM session:
```
!startmsg 123456789
```

2. Send messages directly in the channel:
```
Hello, how can I help you today?
```

3. View user responses in the same channel
4. End the session:
```
!stopmsg
```

## 🤝 Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/improvement`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Create a Pull Request

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⭐ Acknowledgments

- Discord.py library and its contributors
- The Discord developer community
- All contributors to this project
