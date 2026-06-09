#!/bin/bash
# uninstall.sh - Remove dotfiles symlinks and restore backups

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Dotfiles Uninstallation ===${NC}\n"

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

# Function to remove symlink and restore backup
restore_file() {
    local file=$1
    local backup="${file}.backup"
    
    if [ -L "$file" ]; then
        rm "$file"
        print_info "Removed symlink: $file"
        
        if [ -f "$backup" ]; then
            mv "$backup" "$file"
            print_success "Restored backup: $file"
        fi
    elif [ -f "$file" ] && [ -f "$backup" ]; then
        print_warning "$file exists but is not a symlink, backup not restored"
    else
        print_info "$file not found, skipping"
    fi
}

# Confirm uninstallation
echo -e "${YELLOW}This will remove all dotfile symlinks and restore backups.${NC}"
read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_error "Uninstallation cancelled"
    exit 1
fi

echo ""

# Remove symlinks and restore backups
print_info "Removing symlinks and restoring backups..."

restore_file "$HOME/.zshrc"
restore_file "$HOME/.config/starship.toml"
restore_file "$HOME/.gitconfig"
restore_file "$HOME/.tmux.conf"
restore_file "$HOME/.config/Code/User/settings.json"

# Additional backup files to list
print_info "Checking for other backup files..."
backup_count=0
for backup in "$HOME"/.*.backup "$HOME"/.config/*.backup; do
    if [ -f "$backup" ]; then
        print_warning "Found backup: $backup (not automatically restored)"
        backup_count=$((backup_count + 1))
    fi
done

if [ $backup_count -eq 0 ]; then
    print_success "No additional backup files found"
fi

# Remove the shared agent-tools venv (rebuilt by install.sh from tools/requirements.txt).
AGENT_VENV="$HOME/.local/share/dotfiles-agents"
if [ -d "$AGENT_VENV" ]; then
    rm -rf "$AGENT_VENV"
    print_success "Removed agent-tools venv ($AGENT_VENV)"
fi
# Note: paper-scout runtime data (login profile + downloaded PDFs) lives in
# ~/.config/paper-scout (or $PAPER_SCOUT_HOME) and is left in place. Remove manually if desired.

# Note about shell
if [ "$SHELL" = "$(which zsh)" ]; then
    echo ""
    print_info "Your default shell is still Zsh"
    echo -e "  To change back to Bash: ${YELLOW}chsh -s $(which bash)${NC}"
fi

# Note about installed software
echo ""
print_warning "The following software was installed and remains on your system:"
echo "  • Oh-My-Zsh (~/.oh-my-zsh)"
echo "  • Zsh plugins"
echo "  • Starship prompt"
echo "  • NVM (~/.nvm)"
echo "  • System packages (zsh, tmux, fzf, etc.)"
echo ""
echo -e "To remove them manually:"
echo -e "  ${YELLOW}rm -rf ~/.oh-my-zsh ~/.nvm${NC}"
echo -e "  ${YELLOW}sudo apt-get remove starship${NC}"

echo -e "\n${GREEN}=== Uninstallation Complete ===${NC}"
echo -e "${BLUE}Your dotfiles repository at $(dirname "$0") is unchanged.${NC}"
