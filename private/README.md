# Private Directory

This directory contains sensitive configurations that should not be committed to version control.

## Setup

Copy the example files and customize them with your private settings:

```bash
cp vscode-settings.json.example vscode-settings.json
```

Then edit `vscode-settings.json` with your actual API keys and private settings.

## Files

- `vscode-settings.json` - Private VS Code settings (API keys, tokens, etc.)
- `.gitkeep` - Keeps this directory in git

## Important

- Never commit actual private configuration files
- All files in this directory (except `.gitkeep` and `*.example`) are ignored by git
- The install script will merge these settings with public ones
