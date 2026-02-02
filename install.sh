#!/bin/bash
# install.sh - Dotfiles installation script for Linux

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}=== Dotfiles Installation ===${NC}"
echo -e "${BLUE}Installing from: ${DOTFILES_DIR}${NC}\n"

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}→${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Function to backup existing file
backup_file() {
    local file=$1
    if [ -f "$file" ] || [ -L "$file" ]; then
        mv "$file" "${file}.backup"
        print_warning "Backed up existing $file to ${file}.backup"
    fi
}

# Function to create symlink
create_symlink() {
    local source=$1
    local target=$2
    
    # Create target directory if needed
    local target_dir=$(dirname "$target")
    mkdir -p "$target_dir"
    
    # Backup existing file
    backup_file "$target"
    
    # Create symlink
    ln -sf "$source" "$target"
    print_success "Linked $target"
}

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    print_error "This script is designed for Linux only"
    exit 1
fi

# Update package list
print_info "Updating package list..."
sudo apt-get update -qq

# Install essential packages
print_info "Installing essential packages..."
PACKAGES=(
    "zsh"
    "curl"
    "wget"
    "git"
    "tmux"
    "fzf"
    "jq"
    "build-essential"
)

for package in "${PACKAGES[@]}"; do
    if ! dpkg -l | grep -q "^ii  $package "; then
        sudo apt-get install -y "$package"
        print_success "Installed $package"
    else
        print_success "$package already installed"
    fi
done

# Install Oh-My-Zsh
print_info "Installing Oh-My-Zsh..."
if [ ! -d "$HOME/.oh-my-zsh" ]; then
    RUNZSH=no CHSH=no sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
    print_success "Oh-My-Zsh installed"
else
    print_success "Oh-My-Zsh already installed"
fi

# Install Zsh plugins
print_info "Installing Zsh plugins..."

# zsh-autosuggestions
if [ ! -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions" ]; then
    git clone https://github.com/zsh-users/zsh-autosuggestions ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-autosuggestions
    print_success "Installed zsh-autosuggestions"
else
    print_success "zsh-autosuggestions already installed"
fi

# zsh-syntax-highlighting
if [ ! -d "${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting" ]; then
    git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ${ZSH_CUSTOM:-$HOME/.oh-my-zsh/custom}/plugins/zsh-syntax-highlighting
    print_success "Installed zsh-syntax-highlighting"
else
    print_success "zsh-syntax-highlighting already installed"
fi

# Install Starship
print_info "Installing Starship..."
if ! command -v starship &> /dev/null; then
    curl -sS https://starship.rs/install.sh | sh -s -- -y
    print_success "Starship installed"
else
    print_success "Starship already installed"
fi

# Install NVM
print_info "Installing NVM..."
if [ ! -d "$HOME/.nvm" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
    print_success "NVM installed"
else
    print_success "NVM already installed"
fi

# Create symlinks for dotfiles
print_info "Creating symlinks..."
create_symlink "$DOTFILES_DIR/.zshrc" "$HOME/.zshrc"
create_symlink "$DOTFILES_DIR/.config/starship.toml" "$HOME/.config/starship.toml"
create_symlink "$DOTFILES_DIR/.gitconfig" "$HOME/.gitconfig"
create_symlink "$DOTFILES_DIR/.tmux.conf" "$HOME/.tmux.conf"

# Handle VS Code settings with private config support
print_info "Setting up VS Code settings..."
VSCODE_SETTINGS_DIR="$HOME/.config/Code/User"
VSCODE_PUBLIC_SETTINGS="$DOTFILES_DIR/.config/Code/User/settings.json"
VSCODE_PRIVATE_SETTINGS="$DOTFILES_DIR/private/vscode-settings.json"

if [ -f "$VSCODE_PRIVATE_SETTINGS" ]; then
    print_info "Merging public and private VS Code settings..."
    mkdir -p "$VSCODE_SETTINGS_DIR"
    
    # Backup existing settings
    backup_file "$VSCODE_SETTINGS_DIR/settings.json"
    
    # Merge settings using json5 (handles comments in JSON)
    if command -v json5 &> /dev/null; then
        # Convert both files to clean JSON, then merge with jq
        json5 "$VSCODE_PUBLIC_SETTINGS" > /tmp/public.json 2>/dev/null || cp "$VSCODE_PUBLIC_SETTINGS" /tmp/public.json
        json5 "$VSCODE_PRIVATE_SETTINGS" > /tmp/private.json 2>/dev/null || cp "$VSCODE_PRIVATE_SETTINGS" /tmp/private.json
        
        # Check if files are valid and not empty
        PUBLIC_SIZE=$(jq -r 'if . == {} or . == null then "empty" else "valid" end' /tmp/public.json 2>/dev/null || echo "invalid")
        PRIVATE_SIZE=$(jq -r 'if . == {} or . == null then "empty" else "valid" end' /tmp/private.json 2>/dev/null || echo "invalid")
        
        if [ "$PUBLIC_SIZE" = "valid" ] && [ "$PRIVATE_SIZE" = "valid" ]; then
            # Both files have content, merge them
            jq -s '.[0] * .[1]' /tmp/public.json /tmp/private.json > "$VSCODE_SETTINGS_DIR/settings.json"
            print_success "Merged VS Code settings with private config"
        elif [ "$PUBLIC_SIZE" = "valid" ]; then
            # Only public settings are valid
            cp /tmp/public.json "$VSCODE_SETTINGS_DIR/settings.json"
            print_success "Using public VS Code settings (private settings empty)"
        elif [ "$PRIVATE_SIZE" = "valid" ]; then
            # Only private settings are valid
            cp /tmp/private.json "$VSCODE_SETTINGS_DIR/settings.json"
            print_success "Using private VS Code settings"
        else
            # Neither file is valid
            print_warning "No valid VS Code settings found, skipping"
        fi
        
        rm -f /tmp/public.json /tmp/private.json
    else
        print_warning "json5 not found, installing via npm..."
        if command -v npm &> /dev/null; then
            npm install -g json5
            # Retry the merge
            json5 "$VSCODE_PUBLIC_SETTINGS" > /tmp/public.json 2>/dev/null || cp "$VSCODE_PUBLIC_SETTINGS" /tmp/public.json
            json5 "$VSCODE_PRIVATE_SETTINGS" > /tmp/private.json 2>/dev/null || cp "$VSCODE_PRIVATE_SETTINGS" /tmp/private.json
            jq -s '.[0] * .[1]' /tmp/public.json /tmp/private.json > "$VSCODE_SETTINGS_DIR/settings.json"
            rm -f /tmp/public.json /tmp/private.json
            print_success "Merged VS Code settings with private config"
        else
            print_warning "npm not found, using public settings"
            cp "$VSCODE_PUBLIC_SETTINGS" "$VSCODE_SETTINGS_DIR/settings.json"
        fi
    fi
elif [ -f "$VSCODE_PUBLIC_SETTINGS" ]; then
    create_symlink "$VSCODE_PUBLIC_SETTINGS" "$VSCODE_SETTINGS_DIR/settings.json"
else
    print_warning "No VS Code settings found"
fi

# Backup dconf settings
print_info "Backing up dconf settings..."
if command -v dconf &> /dev/null; then
    dconf dump / > "$DOTFILES_DIR/dconf-settings.ini"
    print_success "dconf settings backed up to dconf-settings.ini"
else
    print_warning "dconf not found, skipping backup"
fi

# Change default shell to zsh
print_info "Setting Zsh as default shell..."
if [ "$SHELL" != "$(which zsh)" ]; then
    chsh -s $(which zsh)
    print_success "Default shell changed to Zsh (restart required)"
else
    print_success "Zsh is already the default shell"
fi

echo -e "\n${GREEN}=== Installation Complete ===${NC}"
echo -e "${BLUE}Next steps:${NC}"
echo -e "  1. Restart your terminal or run: ${YELLOW}exec zsh${NC}"
echo -e "  2. Edit ${YELLOW}~/.gitconfig${NC} with your name and email"
echo -e "  3. For private VS Code settings, create ${YELLOW}private/vscode-settings.json${NC}"
echo -e "  4. Configure Brave and Zotero manually as needed"
echo -e "\n${BLUE}Notes:${NC}"
echo -e "  • Your old configs were backed up with ${YELLOW}.backup${NC} extension"
echo -e "  • To restore dconf settings: ${YELLOW}dconf load / < dconf-settings.ini${NC}"
echo -e "  • To uninstall: ${YELLOW}./uninstall.sh${NC}"
