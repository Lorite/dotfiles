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

# Function to backup existing path (file, symlink, or directory)
backup_path() {
	local path=$1
	if [ -e "$path" ] || [ -L "$path" ]; then
		mv "$path" "${path}.backup"
		print_warning "Backed up existing $path to ${path}.backup"
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

# Function to create symlink for any path type (file, symlink, or directory)
create_symlink_path() {
	local source=$1
	local target=$2

	# Create target parent directory if needed
	local target_dir
	target_dir=$(dirname "$target")
	mkdir -p "$target_dir"

	# Backup existing path
	backup_path "$target"

	# Create symlink
	ln -s "$source" "$target"
	print_success "Linked $target"
}

# Normalize Claude frontmatter keys to improve OpenCode compatibility.
normalize_frontmatter_for_opencode() {
	local source_file=$1
	local target_file=$2

	awk '
        function ltrim(s) { sub(/^[[:space:]]+/, "", s); return s }
        function rtrim(s) { sub(/[[:space:]]+$/, "", s); return s }
        function trim(s) { return rtrim(ltrim(s)) }
        function strip_quotes(s) {
            s = trim(s)
            if (s ~ /^".*"$/ || s ~ /^'\''.*'\''$/) {
                s = substr(s, 2, length(s) - 2)
            }
            return s
        }
        function emit_tools_map(raw,   cleaned, n, items, i, item) {
            cleaned = raw
            gsub(/^[[:space:]]*\[/, "", cleaned)
            gsub(/\][[:space:]]*$/, "", cleaned)

            print "tools:"
            n = split(cleaned, items, /,[[:space:]]*/)
            for (i = 1; i <= n; i++) {
                item = strip_quotes(items[i])
                if (item != "") {
                    printf "  \"%s\": true\n", item
                }
            }
        }

        NR == 1 && $0 == "---" {
            in_frontmatter = 1
            print
            next
        }
        in_frontmatter && $0 == "---" {
            in_frontmatter = 0
            print
            next
        }
        in_frontmatter {
            sub(/^argument-hint:/, "argumentHint:")
            sub(/^user-invocable:/, "userInvocable:")
            sub(/^tool-restrictions:/, "toolRestrictions:")

            # Convert Claude-style multi-line tools arrays into OpenCode tools records.
            if (capturing_tools_multiline) {
                if ($0 ~ /^[[:space:]]+-[[:space:]]/) {
                    item = $0
                    sub(/^[[:space:]]+-[[:space:]]/, "", item)
                    item = strip_quotes(trim(item))
                    if (item != "") printf "  \"%s\": true\n", item
                    next
                }
                capturing_tools_multiline = 0
            }
            if ($0 ~ /^tools:[[:space:]]*$/) {
                print "tools:"
                capturing_tools_multiline = 1
                next
            }

            # Convert Claude-style inline tools arrays into OpenCode tools records.
            if (capturing_tools) {
                tools_buf = tools_buf " " $0
                if ($0 ~ /\]/) {
                    emit_tools_map(tools_buf)
                    tools_buf = ""
                    capturing_tools = 0
                }
                next
            }
            if ($0 ~ /^tools:[[:space:]]*\[/) {
                tools_buf = $0
                sub(/^tools:[[:space:]]*/, "", tools_buf)
                if (tools_buf ~ /\]/) {
                    emit_tools_map(tools_buf)
                    tools_buf = ""
                } else {
                    capturing_tools = 1
                }
                next
            }

            # Some source files use model as an array placeholder, which may be invalid.
            if (capturing_model_array) {
                if ($0 ~ /\]/) {
                    capturing_model_array = 0
                }
                next
            }
            if ($0 ~ /^model:[[:space:]]*\[/) {
                if ($0 !~ /\]/) {
                    capturing_model_array = 1
                }
                next
            }

            print
            next
        }
        {
            print
        }
    ' "$source_file" >"$target_file"
}

# Translate the Copilot/VS-Code tool namespace to Claude Code tool names when
# syncing agents to ~/.claude/agents/. Claude filters a spawned subagent's tool
# registry to the names in `tools:`; the lowercase Copilot names (read/execute/…)
# and `server/*` MCP globs match nothing in Claude, so an un-translated agent
# spawns with an EMPTY registry (every tool call no-ops → tool_uses: 0). The main
# session is unaffected because inline work uses the live tools, not this filter —
# which is why spawning broke while inline stayed rock-solid. Mapping: read→Read,
# edit→Edit,Write, execute→Bash, search→Grep,Glob, web→WebFetch,WebSearch,
# todo→TodoWrite, agent→Agent, vscode→(dropped); `<server>/*` → mcp__<server>
# (whole-server form; any char outside [A-Za-z0-9_-] → _). Emits Claude's
# comma-separated string form, deduped; OMITS `tools:` entirely when nothing maps
# (→ subagent inherits all tools). Everything else is passed through verbatim.
normalize_frontmatter_for_claude() {
	local source_file=$1
	local target_file=$2

	awk '
        function ltrim(s) { sub(/^[[:space:]]+/, "", s); return s }
        function rtrim(s) { sub(/[[:space:]]+$/, "", s); return s }
        function trim(s) { return rtrim(ltrim(s)) }
        function strip_quotes(s) {
            s = trim(s)
            if (s ~ /^".*"$/ || s ~ /^'\''.*'\''$/) {
                s = substr(s, 2, length(s) - 2)
            }
            return s
        }
        function map_tool(tok,   srv) {
            tok = strip_quotes(tok)
            if (tok == "") return ""
            if (tok ~ /\/\*$/) {                 # MCP "<server>/*" -> whole server
                srv = tok; sub(/\/\*$/, "", srv)
                gsub(/[^A-Za-z0-9_-]/, "_", srv)
                return "mcp__" srv
            }
            if (tok ~ /\//) { sub(/\/.*$/, "", tok) }  # "ns/subtool" -> map by ns
            if (tok == "read")    return "Read"
            if (tok == "edit")    return "Edit, Write"
            if (tok == "execute") return "Bash"
            if (tok == "search")  return "Grep, Glob"
            if (tok == "web")     return "WebFetch, WebSearch"
            if (tok == "todo")    return "TodoWrite"
            if (tok == "agent")   return "Agent"
            return ""                            # vscode and anything unknown: drop
        }
        function add_mapped(mapped,   m, parts, j, p) {
            if (mapped == "") return
            m = split(mapped, parts, /,[[:space:]]*/)
            for (j = 1; j <= m; j++) {
                p = trim(parts[j])
                if (p == "" || (p in seen)) continue
                seen[p] = 1; order[++ocount] = p
            }
        }
        function flush_tools(   i, out) {
            out = ""
            for (i = 1; i <= ocount; i++)
                out = (out == "") ? order[i] : out ", " order[i]
            if (out != "") print "tools: " out  # else omit -> inherit all tools
            delete seen; delete order; ocount = 0
        }
        function emit_tools_inline(raw,   cleaned, n, items, i) {
            cleaned = raw
            gsub(/^[[:space:]]*\[/, "", cleaned)
            gsub(/\][[:space:]]*$/, "", cleaned)
            delete seen; delete order; ocount = 0
            n = split(cleaned, items, /,[[:space:]]*/)
            for (i = 1; i <= n; i++) add_mapped(map_tool(items[i]))
            flush_tools()
        }

        NR == 1 && $0 == "---" { in_fm = 1; print; next }
        in_fm && $0 == "---" {
            if (capturing_ml) { flush_tools(); capturing_ml = 0 }
            in_fm = 0; print; next
        }
        in_fm {
            if (capturing_ml) {
                if ($0 ~ /^[[:space:]]+-[[:space:]]/) {
                    item = $0; sub(/^[[:space:]]+-[[:space:]]/, "", item)
                    add_mapped(map_tool(item)); next
                }
                flush_tools(); capturing_ml = 0
            }
            if ($0 ~ /^tools:[[:space:]]*$/) {
                delete seen; delete order; ocount = 0; capturing_ml = 1; next
            }
            if (capturing_inline) {
                tools_buf = tools_buf " " $0
                if ($0 ~ /\]/) { emit_tools_inline(tools_buf); tools_buf = ""; capturing_inline = 0 }
                next
            }
            if ($0 ~ /^tools:[[:space:]]*\[/) {
                tools_buf = $0; sub(/^tools:[[:space:]]*/, "", tools_buf)
                if (tools_buf ~ /\]/) { emit_tools_inline(tools_buf); tools_buf = "" }
                else capturing_inline = 1
                next
            }
            print; next
        }
        { print }
    ' "$source_file" >"$target_file"
}

# Sync Copilot customizations to Claude paths using Claude CLI format.
sync_copilot_to_claude() {
	local source_dir=$1
	local target_dir=$2
	local label=$3

	if [ ! -d "$source_dir" ]; then
		print_warning "No $label found at $source_dir, skipping"
		return
	fi

	if [ -L "$target_dir" ]; then
		backup_path "$target_dir"
	fi

	# Use symlink for skills (same format for Claude, Copilot, OpenCode)
	if [[ "$target_dir" == *"skills" ]]; then
		ln -sf "$source_dir" "$target_dir"
		print_success "Linked $label to $target_dir"
		return
	fi

	mkdir -p "$target_dir"

	find "$source_dir" -type f | while IFS= read -r source_file; do
		local relative_path="${source_file#$source_dir/}"
		local target_file="$target_dir/$relative_path"
		local target_parent
		target_parent=$(dirname "$target_file")

		mkdir -p "$target_parent"
		if [[ "$source_file" == *.agent.md ]]; then
			normalize_frontmatter_for_claude "$source_file" "$target_file"
		else
			cp "$source_file" "$target_file"
		fi
	done

	print_success "Synced $label to $target_dir"
}

# Sync Copilot customizations to OpenCode paths using compatibility transforms.
sync_copilot_to_opencode() {
	local source_dir=$1
	local target_dir=$2
	local label=$3

	if [ ! -d "$source_dir" ]; then
		print_warning "No $label found at $source_dir, skipping"
		return
	fi

	# Use symlink for skills (same format for Claude, Copilot, OpenCode)
	if [[ "$target_dir" == *"skills" ]]; then
		if [ -L "$target_dir" ]; then
			backup_path "$target_dir"
		fi
		ln -sf "$source_dir" "$target_dir"
		print_success "Linked $label to $target_dir"
		return
	fi

	if [ -L "$target_dir" ]; then
		backup_path "$target_dir"
	fi

	mkdir -p "$target_dir"

	find "$source_dir" -type f | while IFS= read -r source_file; do
		local relative_path="${source_file#$source_dir/}"
		local target_file="$target_dir/$relative_path"
		local target_parent
		target_parent=$(dirname "$target_file")

		mkdir -p "$target_parent"
		normalize_frontmatter_for_opencode "$source_file" "$target_file"
	done

	print_success "Synced $label to $target_dir"
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
	"python3-venv"
	"python3-pip"
	"rclone"
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
if ! command -v starship &>/dev/null; then
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
	if command -v json5 &>/dev/null; then
		# Convert both files to clean JSON, then merge with jq
		json5 "$VSCODE_PUBLIC_SETTINGS" >/tmp/public.json 2>/dev/null || cp "$VSCODE_PUBLIC_SETTINGS" /tmp/public.json
		json5 "$VSCODE_PRIVATE_SETTINGS" >/tmp/private.json 2>/dev/null || cp "$VSCODE_PRIVATE_SETTINGS" /tmp/private.json

		# Check if files are valid and not empty
		PUBLIC_SIZE=$(jq -r 'if . == {} or . == null then "empty" else "valid" end' /tmp/public.json 2>/dev/null || echo "invalid")
		PRIVATE_SIZE=$(jq -r 'if . == {} or . == null then "empty" else "valid" end' /tmp/private.json 2>/dev/null || echo "invalid")

		if [ "$PUBLIC_SIZE" = "valid" ] && [ "$PRIVATE_SIZE" = "valid" ]; then
			# Both files have content, merge them
			jq -s '.[0] * .[1]' /tmp/public.json /tmp/private.json >"$VSCODE_SETTINGS_DIR/settings.json"
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
		if command -v npm &>/dev/null; then
			npm install -g json5
			# Retry the merge
			json5 "$VSCODE_PUBLIC_SETTINGS" >/tmp/public.json 2>/dev/null || cp "$VSCODE_PUBLIC_SETTINGS" /tmp/public.json
			json5 "$VSCODE_PRIVATE_SETTINGS" >/tmp/private.json 2>/dev/null || cp "$VSCODE_PRIVATE_SETTINGS" /tmp/private.json
			jq -s '.[0] * .[1]' /tmp/public.json /tmp/private.json >"$VSCODE_SETTINGS_DIR/settings.json"
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
if command -v dconf &>/dev/null; then
	mkdir -p "$DOTFILES_DIR/private"
	dconf dump / >"$DOTFILES_DIR/private/dconf-settings.ini"
	print_success "dconf settings backed up to private/dconf-settings.ini"
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

# Install OpenCode
print_info "Installing OpenCode..."
OPENCODE_INSTALL_DIR="$HOME/.local/bin"
mkdir -p "$OPENCODE_INSTALL_DIR"
if command -v opencode &>/dev/null || [ -x "$HOME/.opencode/bin/opencode" ] || [ -x "$OPENCODE_INSTALL_DIR/opencode" ]; then
	OPENCODE_PATH=$(command -v opencode 2>/dev/null || true)
	if [ -z "$OPENCODE_PATH" ] && [ -x "$HOME/.opencode/bin/opencode" ]; then
		OPENCODE_PATH="$HOME/.opencode/bin/opencode"
	elif [ -z "$OPENCODE_PATH" ] && [ -x "$OPENCODE_INSTALL_DIR/opencode" ]; then
		OPENCODE_PATH="$OPENCODE_INSTALL_DIR/opencode"
	fi
	print_success "OpenCode already installed (${OPENCODE_PATH})"
else
	if curl -fsSL https://opencode.ai/install | bash -s -- -b "$OPENCODE_INSTALL_DIR"; then
		print_success "OpenCode installed to $OPENCODE_INSTALL_DIR"
	else
		print_warning "Install with custom bin dir failed, retrying default OpenCode install location..."
		curl -fsSL https://opencode.ai/install | bash
		print_success "OpenCode installed"
	fi
fi

# Ensure OpenCode paths are in PATH for zsh
print_info "Ensuring OpenCode paths are in PATH for zsh..."
for opencode_path in '$HOME/.local/bin' '$HOME/.opencode/bin'; do
	if ! grep -Fq "$opencode_path" "$HOME/.zshrc" 2>/dev/null; then
		echo "export PATH=\"${opencode_path}:\$PATH\"" >>"$HOME/.zshrc"
		print_success "Added ${opencode_path} to PATH in .zshrc"
	fi
done

# Setup Copilot, OpenCode, and Claude config.
print_info "Setting up GitHub Copilot, OpenCode, and Claude configuration..."
mkdir -p "$DOTFILES_DIR/.copilot/agents"
mkdir -p "$DOTFILES_DIR/.copilot/skills"

# VS Code user-level custom agent location.
mkdir -p "$HOME/.copilot"
create_symlink_path "$DOTFILES_DIR/.copilot/agents" "$HOME/.copilot/agents"
create_symlink_path "$DOTFILES_DIR/.copilot/skills" "$HOME/.copilot/skills"

# Claude uses transformed copies from .copilot source.
mkdir -p "$HOME/.claude"
# Claude user settings (sandbox allowlist etc.) — tracked here, symlinked (Claude-only, not synced to Copilot/OpenCode).
create_symlink "$DOTFILES_DIR/.claude/settings.json" "$HOME/.claude/settings.json"
sync_copilot_to_claude "$DOTFILES_DIR/.copilot/agents" "$HOME/.claude/agents" "Copilot agents"
sync_copilot_to_claude "$DOTFILES_DIR/.copilot/skills" "$HOME/.claude/skills" "Copilot skills"

# OpenCode uses transformed copies from .copilot source.
mkdir -p "$HOME/.config/opencode"
create_symlink "$DOTFILES_DIR/.copilot/CLAUDE.md" "$HOME/.config/opencode/AGENTS.md"
sync_copilot_to_opencode "$DOTFILES_DIR/.copilot/agents" "$HOME/.config/opencode/agents" "Copilot agents"
sync_copilot_to_opencode "$DOTFILES_DIR/.copilot/skills" "$HOME/.config/opencode/skills" "Copilot skills"

# Setup VS Code global prompt files.
mkdir -p "$DOTFILES_DIR/.vscode/prompts"
create_symlink_path "$DOTFILES_DIR/.vscode/prompts" "$HOME/.config/Code/User/prompts"

print_success "OpenCode and VS Code configured with dotfiles as source of truth"

# Setup shared Python venv for agent tooling (paper-scout, and future agents).
print_info "Setting up agent-tools Python venv..."
AGENT_VENV="$HOME/.local/share/dotfiles-agents/venv"
AGENT_REQS="$DOTFILES_DIR/tools/requirements.txt"
if [ -f "$AGENT_REQS" ]; then
	if [ ! -d "$AGENT_VENV" ]; then
		python3 -m venv "$AGENT_VENV"
		print_success "Created agent-tools venv at $AGENT_VENV"
	fi
	"$AGENT_VENV/bin/pip" install -q --upgrade pip >/dev/null 2>&1 || true
	if "$AGENT_VENV/bin/pip" install -q -r "$AGENT_REQS"; then
		print_success "Installed agent-tools Python deps (tools/requirements.txt)"
	else
		print_warning "Failed to install some agent-tools Python deps"
	fi
	# paper-scout drives system Google Chrome (Playwright channel=chrome); no browser download.
	if ! command -v google-chrome &>/dev/null && ! command -v google-chrome-stable &>/dev/null; then
		print_warning "Google Chrome not found — paper-scout PDF fetch needs it (https://www.google.com/chrome/)"
	fi
else
	print_warning "No $AGENT_REQS found — skipping agent-tools venv"
fi

# task-manager: mdbase-tasknotes (mtn) is a standalone CLI over the Obsidian TaskNotes vault.
print_info "Installing mdbase-tasknotes (mtn) CLI..."
if command -v npm &>/dev/null; then
	if command -v mtn &>/dev/null; then
		print_success "mdbase-tasknotes already installed ($(command -v mtn))"
	elif npm install -g mdbase-tasknotes >/dev/null 2>&1; then
		print_success "Installed mdbase-tasknotes (mtn)"
	else
		print_warning "Failed to install mdbase-tasknotes — run 'npm i -g mdbase-tasknotes' manually"
	fi
else
	print_warning "npm not found — skipping mdbase-tasknotes (needed by task-manager)"
fi

# Install uv (Python package manager, needed for mcp-libre Python 3.12 venv).
print_info "Installing uv (Python package manager)..."
if command -v uv &>/dev/null; then
	print_success "uv already installed ($(uv --version))"
else
	if curl -LsSf https://astral.sh/uv/install.sh | sh; then
		export PATH="$HOME/.local/bin:$PATH"
		print_success "uv installed"
	else
		print_warning "Failed to install uv — mcp-libre setup will be skipped"
	fi
fi

# Install mcp-libre (LibreOffice MCP server used by lorite-recurring-meeting-docx skill).
print_info "Installing mcp-libre (LibreOffice MCP server)..."
MCP_LIBRE_DIR="$HOME/.local/lib/mcp-libre"
if ! command -v libreoffice &>/dev/null; then
	print_warning "LibreOffice not found — skipping mcp-libre (install LibreOffice, then re-run install.sh)"
elif ! command -v uv &>/dev/null; then
	print_warning "uv not found — skipping mcp-libre setup"
else
	# Clone
	if [ ! -d "$MCP_LIBRE_DIR" ]; then
		git clone https://github.com/jwingnut/mcp-libre.git "$MCP_LIBRE_DIR"
		print_success "Cloned mcp-libre to $MCP_LIBRE_DIR"
	else
		print_success "mcp-libre already cloned at $MCP_LIBRE_DIR"
	fi

	# Build and install the LibreOffice .oxt extension
	if unopkg list 2>/dev/null | grep -q "org.mcp.libreoffice"; then
		print_success "mcp-libre LibreOffice extension already installed"
	else
		(cd "$MCP_LIBRE_DIR/plugin" && bash build.sh >/dev/null 2>&1)
		if unopkg add "$MCP_LIBRE_DIR/build/libreoffice-mcp-extension-1.0.0.oxt" 2>/dev/null; then
			print_success "mcp-libre LibreOffice extension installed"
		else
			print_warning "Failed to install mcp-libre .oxt — try: unopkg add $MCP_LIBRE_DIR/build/libreoffice-mcp-extension-1.0.0.oxt"
		fi
	fi

	# Create Python 3.12 venv with fastmcp + httpx (the FastMCP bridge for Claude Code)
	if [ ! -d "$MCP_LIBRE_DIR/.venv" ]; then
		uv venv --python 3.12 "$MCP_LIBRE_DIR/.venv" >/dev/null 2>&1
		uv pip install --python "$MCP_LIBRE_DIR/.venv/bin/python" fastmcp httpx >/dev/null 2>&1
		print_success "mcp-libre Python 3.12 venv created"
	else
		print_success "mcp-libre Python venv already exists"
	fi

	# Register the FastMCP bridge with Claude Code at user scope
	if command -v claude &>/dev/null; then
		if claude mcp list 2>/dev/null | grep -q "^libreoffice:"; then
			print_success "mcp-libre already registered with Claude Code"
		elif claude mcp add --scope user libreoffice -- \
			"$MCP_LIBRE_DIR/.venv/bin/fastmcp" run "$MCP_LIBRE_DIR/libreoffice_mcp_server.py" 2>/dev/null; then
			print_success "mcp-libre registered with Claude Code (user scope)"
		else
			print_warning "Failed to register mcp-libre with Claude Code — run manually: claude mcp add --scope user libreoffice -- $MCP_LIBRE_DIR/.venv/bin/fastmcp run $MCP_LIBRE_DIR/libreoffice_mcp_server.py"
		fi
	else
		print_warning "claude CLI not found — skipping Claude Code MCP registration (re-run install.sh after installing Claude Code)"
	fi
fi

# Install zotero-mcp (Zotero MCP server used by lorite-paper-reader — pilot, 2026-06).
# Repo github.com/54yyyu/zotero-mcp publishes to PyPI as `zotero-mcp-server` (the name mismatch
# is legitimate — verified against its pyproject). The launcher tools/paper-reader/zotero-mcp.sh
# runs it in hybrid mode (read local Zotero API, write via the Web key) and keeps the key out of
# every MCP-client config.
print_info "Installing zotero-mcp (Zotero MCP server)..."
ZOTERO_MCP_LAUNCHER="$DOTFILES_DIR/tools/paper-reader/zotero-mcp.sh"
if ! command -v uv &>/dev/null; then
	print_warning "uv not found — skipping zotero-mcp setup"
else
	if command -v zotero-mcp &>/dev/null; then
		print_success "zotero-mcp already installed ($(zotero-mcp version 2>/dev/null | head -1))"
	elif uv tool install "zotero-mcp-server[all] @ git+https://github.com/54yyyu/zotero-mcp" >/dev/null 2>&1; then
		print_success "zotero-mcp installed (zotero-mcp-server[all] from GitHub)"
	else
		print_warning "Failed to install zotero-mcp — run manually: uv tool install 'zotero-mcp-server[all] @ git+https://github.com/54yyyu/zotero-mcp'"
	fi
	chmod +x "$ZOTERO_MCP_LAUNCHER" 2>/dev/null || true
	# Register with Claude Code at user scope (hybrid mode via the launcher's env)
	if command -v claude &>/dev/null && command -v zotero-mcp &>/dev/null; then
		if claude mcp list 2>/dev/null | grep -q "^zotero:"; then
			print_success "zotero-mcp already registered with Claude Code"
		elif claude mcp add --scope user zotero -- "$ZOTERO_MCP_LAUNCHER" 2>/dev/null; then
			print_success "zotero-mcp registered with Claude Code (user scope)"
		else
			print_warning "Failed to register zotero-mcp — run manually: claude mcp add --scope user zotero -- $ZOTERO_MCP_LAUNCHER"
		fi
	fi
	# One-time: requires a write-enabled Zotero Web API key at ~/.config/paper-scout/zotero-api-key
	# and the semantic-search DB built once with: zotero-mcp update-db  (status: zotero-mcp db-status)
fi

echo -e "\n${GREEN}=== Installation Complete ===${NC}"
echo -e "${BLUE}Next steps:${NC}"
echo -e "  1. Restart your terminal or run: ${YELLOW}exec zsh${NC}"
echo -e "  2. Edit ${YELLOW}~/.gitconfig${NC} with your name and email"
echo -e "  3. For private VS Code settings, create ${YELLOW}private/vscode-settings.json${NC}"
echo -e "  4. Configure Brave and Zotero manually as needed"
echo -e "\n${BLUE}Notes:${NC}"
echo -e "  • Your old configs were backed up with ${YELLOW}.backup${NC} extension"
echo -e "  • To restore dconf settings: ${YELLOW}dconf load / < private/dconf-settings.ini${NC}"
echo -e "  • To uninstall: ${YELLOW}./uninstall.sh${NC}"
