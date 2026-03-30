# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi

# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH

# Path to your oh-my-zsh installation.
export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/robbyrussell/oh-my-zsh/wiki/Themes
ZSH_THEME=""

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in ~/.oh-my-zsh/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment the following line to disable bi-weekly auto-update checks.
DISABLE_AUTO_UPDATE="false"

# Uncomment the following line to automatically update without prompting.
# DISABLE_UPDATE_PROMPT="true"

# Uncomment the following line to change how often to auto-update (in days).
# export UPDATE_ZSH_DAYS=13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS=true

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
HIST_STAMPS="yyyy-mm-dd'T'%H:%M:%S"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in ~/.oh-my-zsh/plugins/*
# Custom plugins may be added to ~/.oh-my-zsh/custom/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(git zsh-autosuggestions zsh-syntax-highlighting bazel tmux nvm colorize history fzf gh autoupdate)

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='mvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"

# import env
if [ -f .env ]; then
    source .env
fi
if [ -f .env.secrets ]; then
    source .env.secrets
fi

# aliases
alias clean_squash_merged_local_git_branches='git checkout -q main && git for-each-ref refs/heads/ \"--format=%(refname:short)\" | while read branch; do mergeBase=\$(git merge-base main \$branch) && [[ \$(git cherry main \$(git commit-tree \$(git rev-parse \"\$branch^{tree}\") -p \$mergeBase -m _)) == \"-\"* ]] && git branch -D \$branch; done'
alias clean_squash_merged_local_git_branches_dry_run='git checkout -q main && git for-each-ref refs/heads/ \"--format=%(refname:short)\" | while read branch; do mergeBase=\$(git merge-base main \$branch) && [[ \$(git cherry main \$(git commit-tree \$(git rev-parse \"\$branch^{tree}\") -p \$mergeBase -m _)) == \"-\"* ]] && echo \"\$branch is merged into main and can be deleted\"; done'

# source dev container specific zshrc if it exists
if [ -n "$REMOTE_CONTAINERS" ] || [ -f /.dockerenv ] || [ -d /workspaces ]; then
    # Try to find .devcontainer/.zshrc in workspaces directory
    for workspace_dir in /workspaces/*; do
        if [ -f "$workspace_dir/.devcontainer/.zshrc" ]; then
            source "$workspace_dir/.devcontainer/.zshrc"
            break
        fi
    done
fi

# source vte for terminal notifications
if [ -f /etc/profile.d/vte-2.91.sh ]; then
    . /etc/profile.d/vte-2.91.sh;
fi
if [ -f /etc/profile.d/vte.sh ]; then
    . /etc/profile.d/vte.sh;
fi

# go
export PATH=$PATH:/usr/local/go/bin

# show hidden files for `cd` etc
setopt globdots

# Start the tmux session if not alraedy in the tmux session
# if [ "$TMUX" = "" ]; then tmux new \; set-option destroy-unattached; fi
# COULDN'T GET IT TO WORK :(

. "$HOME/.local/bin/env"

# opencode
export PATH=/home/$USER/.opencode/bin:$PATH

# starship
eval "$(starship init zsh)"
export PATH="$HOME/.opencode/bin:$PATH"

# obsidian clipper
export OBSIDIAN_CLIPPER_HOME="/home/$USER/git/obsidian-clipper/dist"
export PATH="$OBSIDIAN_CLIPPER_HOME:$PATH"
