# Dotfiles

Personal Linux dotfiles and system configuration management.

## Features

- **Shell**: Zsh with Oh-My-Zsh framework and custom plugins
- **Prompt**: Starship with Dracula theme and ROS 2 integration
- **Terminal**: Tmux configuration for productivity
- **Version Control**: Git with useful aliases and settings
- **Editor**: VS Code settings (with private config support)
- **System**: Ubuntu dconf settings backup/restore (private)
- **Applications**: Configuration for Brave browser and Zotero

## Prerequisites

- Linux (Ubuntu/Debian-based distribution)
- `git` installed
- `curl` or `wget`
- `sudo` access for package installation

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Lorite/dotfiles.git ~/.dotfiles
cd ~/.dotfiles

# Run installation script
./install.sh
```

## What Gets Installed

### Automatic Installation
- **Oh-My-Zsh**: Zsh framework with plugins
- **Zsh Plugins**: 
  - zsh-autosuggestions
  - zsh-syntax-highlighting
- **Starship**: Cross-shell prompt
- **NVM**: Node Version Manager
- **FZF**: Fuzzy finder

### Symlinked Configurations
- `.zshrc` → Shell configuration
- `.config/starship.toml` → Prompt configuration
- `.gitconfig` → Git configuration
- `.tmux.conf` → Tmux configuration
- `.config/Code/User/settings.json` → VS Code settings (if using private config)

### System Backups
- Ubuntu dconf settings saved to `private/dconf-settings.ini` (ignored by git)

## Private Configuration

Sensitive configurations (like VS Code settings with API keys) should be placed in the `private/` directory, which is ignored by git.

### Setup Private Configs

1. Copy the example template:
   ```bash
   cp private/vscode-settings.json.example private/vscode-settings.json
   ```

2. Edit `private/vscode-settings.json` with your private settings

3. The install script will merge private settings with public ones

## Manual Configuration

### Brave Browser
- Settings sync should be configured manually through Brave Sync
- Alternatively, export/import bookmarks from `brave://bookmarks`

### Zotero
- Data directory: Consider symlinking `~/.zotero` or using Zotero sync
- Better BibTeX and other plugins need manual installation

## Directory Structure

```
dotfiles/
├── install.sh              # Main installation script
├── uninstall.sh           # Remove symlinks and restore backups
├── README.md              # This file
├── .gitignore             # Git ignore rules
├── .zshrc                 # Zsh configuration
├── .gitconfig             # Git configuration
├── .tmux.conf             # Tmux configuration
├── .config/
│   ├── starship.toml      # Starship prompt config
│   └── Code/
│       └── User/
│           └── settings.json  # VS Code settings (public)
└── private/               # Private configs (not tracked)
    ├── vscode-settings.json.example
    └── dconf-settings.ini.example
```

## Uninstalling

To remove all symlinks and restore backed-up configurations:

```bash
./uninstall.sh
```

## Customization

Edit the configuration files directly in this repository, then commit and push changes. On other machines, simply `git pull` to sync updates.

## Notes

- The install script creates backups of existing configurations before symlinking
- Backups are stored with `.backup` extension
- Private configurations are never committed to the repository
- dconf settings are private, system-specific, and may need manual review before restoring

## License

MIT License - Feel free to use and modify as needed.
