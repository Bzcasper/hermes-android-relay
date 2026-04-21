#!/bin/bash
# Push Hermes Android Relay to GitHub and deploy to Render

set -e

REPO_NAME="hermes-android-relay"
GITHUB_USER="YOUR_GITHUB_USERNAME"  # UPDATE THIS

echo "============================================================"
echo "HERMES ANDROID RELAY - GitHub + Render Setup"
echo "============================================================"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo "⚠️  GitHub CLI (gh) not installed. Installing..."
    # Install gh CLI for the user without sudo
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
        dd of=/tmp/githubcli-archive-keyring.gpg 2>/dev/null
    mkdir -p ~/.local/share/keyrings
    cp /tmp/githubcli-archive-keyring.gpg ~/.local/share/keyrings/
    # Add to PATH
    export PATH="$HOME/.local/bin:$PATH"
fi

# Check if git is configured
if ! git config --global user.email &>/dev/null; then
    echo "⚠️  Git user not configured"
    echo "Run: git config --global user.email 'you@example.com'"
    echo "     git config --global user.name 'Your Name'"
    exit 1
fi

echo "Step 1: Create GitHub repository"
echo "--------------------------------"

# Authenticate with GitHub
echo "Opening GitHub authentication..."
gh auth login --web 2>/dev/null || {
    echo "Please authenticate manually:"
    echo "  gh auth login --with-token < your_token.txt"
    echo "  Get token at: https://github.com/settings/tokens"
}

# Create repository
echo "Creating repository: $GITHUB_USER/$REPO_NAME"
gh repo create "$REPO_NAME" \
    --description "WebSocket relay for hermes-android - Render Free Tier" \
    --public \
    --source=. \
    --remote=origin \
    --push 2>/dev/null || {
    echo "⚠️  Repo may already exist or manual push needed"
}

# Push to main branch
echo "Pushing code..."
git push -u origin main || git push -u origin master

echo ""
echo "Step 2: Enable GitHub Pages (optional, for docs)"
echo "--------------------------------------------------"
# GitHub Pages not needed for relay but useful for status

echo ""
echo "Step 3: Create Render service"
echo "-------------------------------"
echo ""
echo "Option A: Use Render Dashboard (recommended)"
echo "  1. Go to https://dashboard.render.com"
echo "  2. Click 'New' → 'Web Service'"
echo "  3. Select 'Build and deploy from a Git repository'"
echo "  4. Connect your GitHub account"
echo "  5. Select: $GITHUB_USER/$REPO_NAME"
echo "  6. Configure:"
echo "     - Name: hermes-android-relay"
echo "     - Region: Choose closest to you"
echo "     - Branch: main"
echo "     - Runtime: Python"
echo "     - Build Command: pip install -r requirements.txt"
echo "     - Start Command: python hermes_android_relay/relay.py"
echo "     - Plan: Free"
echo "  7. Add Environment Variable:"
echo "     - PAIRING_CODE = DIWF4P"
echo "  8. Click 'Create Web Service'"
echo ""
echo "Option B: Use render.yaml (automatic)"
echo "  Render will auto-detect render.yaml and configure service"
echo ""

# Check if Render CLI is installed
if command -v render &> /dev/null; then
    echo "Render CLI detected! Attempting deploy..."
    render deploy --confirm 2>/dev/null || {
        echo "Render deploy requires authentication"
        echo "Run: render login"
    }
else
    echo "Install Render CLI: https://render.com/docs/cli"
fi

echo ""
echo "============================================================"
echo "SETUP COMPLETE!"
echo "============================================================"
echo ""
echo "Your repository: https://github.com/$GITHUB_USER/$REPO_NAME"
echo "Pairing Code: DIWF4P"
echo ""
echo "Next steps:"
echo "  1. Wait for Render deployment (~2-3 minutes)"
echo "  2. Get your Render URL from dashboard"
echo "  3. On phone, open Hermes Bridge app"
echo "  4. Enter Relay URL: wss://your-app.onrender.com/ws"
echo "  5. Enter Pairing Code: DIWF4P"
echo "  6. Tap Connect"
echo ""
echo "Test:"
echo "  curl https://your-app.onrender.com/health"
echo ""
