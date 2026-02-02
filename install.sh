#!/bin/bash
# install.sh

# Symlink config files from the cloned repo to the container's home
ln -sf ~/dotfiles/.zshrc ~/.zshrc
mkdir -p ~/.config
ln -sf ~/dotfiles/.config/starship.toml ~/.config/starship.toml

# Install Starship (if not already there)
if ! command -v starship &> /dev/null; then
    curl -sS https://starship.rs/install.sh | sh -s -- -y
fi
