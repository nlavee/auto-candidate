#!/bin/bash

# AutoCandidate Interactive Runner
# This script provides an interactive menu to run AutoCandidate
#
# Features:
# - Tab completion for file and directory paths
# - Optional fzf integration for directory browsing (if installed)
# - Interactive configuration with sensible defaults

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Helper function to read path with autocomplete
read_path() {
    local prompt="$1"
    local default="$2"
    local result

    # Enable readline and file completion
    if [ -n "$default" ]; then
        read -e -p "$prompt [$default]: " result
        result=${result:-$default}
    else
        read -e -p "$prompt: " result
    fi

    echo "$result"
}

# Helper function to select directory with fzf if available
select_directory() {
    local prompt="$1"
    local start_dir="${2:-.}"

    # Check if fzf is available
    if command -v fzf &> /dev/null; then
        echo ""
        print_info "Tip: You can use fzf to browse directories, or type/paste a path directly"
        echo "  [f] Browse with fzf"
        echo "  [t] Type/paste path"
        read -p "Choose [f/t]: " choice

        if [[ "$choice" =~ ^[Ff]$ ]]; then
            # Use fzf to select directory
            local selected
            selected=$(find "$start_dir" -type d 2>/dev/null | fzf --height 40% --reverse --border --prompt="Select directory: ")
            if [ -n "$selected" ]; then
                echo "$selected"
                return
            fi
        fi
    fi

    # Fallback to regular input with tab completion
    read_path "$prompt"
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_error "Virtual environment not found!"
    print_info "Please run setup.sh first: ./setup.sh"
    exit 1
fi

# Activate virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    print_info "Activating virtual environment..."
    source venv/bin/activate
else
    print_success "Virtual environment already active"
fi

# Load .env file if it exists
if [ -f ".env" ]; then
    print_success "Found .env file, API keys will be loaded automatically"
else
    # Check for API keys in environment
    if [[ -z "$GEMINI_API_KEY" ]] && [[ -z "$ANTHROPIC_API_KEY" ]]; then
        print_warning "No API keys found in environment or .env file"
        print_info "You can:"
        print_info "  1. Create a .env file with GEMINI_API_KEY and/or ANTHROPIC_API_KEY"
        print_info "  2. Export them: export GEMINI_API_KEY='your-key'"
        echo ""
    fi
fi

# Main menu
print_header "AutoCandidate - Interactive Runner"
echo ""
echo "What would you like to do?"
echo ""
echo "  1) Start a new run (or resume from checkpoint)"
echo "  2) Check checkpoint status"
echo "  3) Clear checkpoint"
echo "  4) View checkpoint info"
echo "  5) Exit"
echo ""
read -p "Enter your choice [1-5]: " main_choice

case $main_choice in
    1)
        # Start command - interactive configuration
        print_header "Configure AutoCandidate Run"
        echo ""

        # Prompt file
        print_info "Tab completion is enabled for path inputs"
        echo ""
        prompt_file=$(read_path "Enter path to prompt file (e.g., prompt.md)")
        if [ ! -f "$prompt_file" ]; then
            print_warning "Prompt file not found at: $prompt_file"
            read -p "Continue anyway? (y/n): " continue_choice
            if [[ ! "$continue_choice" =~ ^[Yy]$ ]]; then
                print_info "Exiting..."
                exit 0
            fi
        fi

        # Repository source
        echo ""
        echo "Repository source:"
        echo "  1) Local directory"
        echo "  2) Remote Git URL"
        read -p "Choose [1-2]: " repo_choice

        cmd="python auto_candidate/main.py start \"$prompt_file\""

        if [ "$repo_choice" == "1" ]; then
            echo ""
            local_path=$(select_directory "Enter local repository path")
            cmd="$cmd --local-path \"$local_path\""
        else
            echo ""
            read -p "Enter Git repository URL: " repo_url
            cmd="$cmd --repo-url \"$repo_url\""
        fi

        # Workspace
        echo ""
        workspace=$(read_path "Workspace directory" "./workspace")
        if [ "$workspace" != "./workspace" ]; then
            cmd="$cmd --workspace \"$workspace\""
        fi

        # Resume mode
        echo ""
        read -p "Resume from checkpoint if available? (y/n) [n]: " resume_choice
        if [[ "$resume_choice" =~ ^[Yy]$ ]]; then
            cmd="$cmd --resume"
        fi

        # Agent selection
        echo ""
        echo "Agent Configuration:"
        echo "  1) Use Gemini for all phases (default)"
        echo "  2) Use Claude for all phases"
        echo "  3) Custom configuration (choose per phase)"
        read -p "Choose [1-3]: " agent_choice

        case $agent_choice in
            2)
                cmd="$cmd --planning-agent claude --execution-agent claude --integration-agent claude --verification-agent claude"
                ;;
            3)
                echo ""
                echo "Select agent for each phase (gemini/claude):"
                read -p "Planning agent [gemini]: " planning_agent
                planning_agent=${planning_agent:-gemini}
                if [ "$planning_agent" != "gemini" ]; then
                    cmd="$cmd --planning-agent $planning_agent"
                fi

                read -p "Execution agent [gemini]: " execution_agent
                execution_agent=${execution_agent:-gemini}
                if [ "$execution_agent" != "gemini" ]; then
                    cmd="$cmd --execution-agent $execution_agent"
                fi

                read -p "Integration agent [gemini]: " integration_agent
                integration_agent=${integration_agent:-gemini}
                if [ "$integration_agent" != "gemini" ]; then
                    cmd="$cmd --integration-agent $integration_agent"
                fi

                read -p "Verification agent [gemini]: " verification_agent
                verification_agent=${verification_agent:-gemini}
                if [ "$verification_agent" != "gemini" ]; then
                    cmd="$cmd --verification-agent $verification_agent"
                fi
                ;;
            *)
                # Default: use gemini for all (no flags needed)
                ;;
        esac

        # Model selection
        echo ""
        read -p "Specify model name (or press Enter to select interactively): " model_name
        if [ ! -z "$model_name" ]; then
            cmd="$cmd --model \"$model_name\""
        fi

        # Show command and confirm
        echo ""
        print_header "Ready to Execute"
        echo ""
        print_info "Command:"
        echo -e "${YELLOW}$cmd${NC}"
        echo ""
        read -p "Execute this command? (y/n) [y]: " confirm
        confirm=${confirm:-y}

        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            echo ""
            print_success "Starting AutoCandidate..."
            echo ""
            eval $cmd
        else
            print_info "Cancelled by user"
        fi
        ;;

    2)
        # Checkpoint status
        workspace=$(read_path "Workspace directory" "./workspace")

        print_info "Checking checkpoint status..."
        python auto_candidate/main.py checkpoint-status --workspace "$workspace"
        ;;

    3)
        # Clear checkpoint
        workspace=$(read_path "Workspace directory" "./workspace")

        read -p "Are you sure you want to clear the checkpoint? (y/n): " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            python auto_candidate/main.py checkpoint-clear --workspace "$workspace"
        else
            print_info "Cancelled"
        fi
        ;;

    4)
        # View checkpoint info
        workspace=$(read_path "Workspace directory" "./workspace")

        print_info "Fetching checkpoint info..."
        python auto_candidate/main.py checkpoint-info --workspace "$workspace"
        ;;

    5)
        print_info "Exiting..."
        exit 0
        ;;

    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

echo ""
print_success "Done!"
