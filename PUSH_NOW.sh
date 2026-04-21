#!/bin/bash
# Automated push to GitHub - run this from your machine

set -e

GITHUB_USER="${GITHUB_USER:-YOUR_GITHUB_USERNAME}"

echo "=============================================="
echo "PUSHING HERMES-ANDROID-RELAY TO GITHUB"
echo "=============================================="
echo ""

# Check for gh CLI
if command -v gh &> /dev/null; then
    echo "GitHub CLI detected!"
    
    # Check auth
    if ! gh auth status &>/dev/null; then
        echo "Not authenticated. Run: gh auth login"
        exit 1
    fi
    
    # Create repo and push
    echo "Creating repository: hermes-android-relay"
    gh repo create hermes-android-relay \
        --description "WebSocket relay for hermes-android - Render Free Tier" \
        --public \
        --source=. \
        --push \
        2>/dev/null || {
        echo "Repo may exist, trying push..."
    }
    
    echo "✅ Repository created and pushed!"
    echo ""
    echo "URL: https://github.com/$(gh api user -q .login)/hermes-android-relay"
    
else
    echo "GitHub CLI not available. Manual instructions:"
    echo ""
    echo "1. Create repo at: https://github.com/new"
    echo "2. Name: hermes-android-relay"
    echo "3. Set as Public"
    echo "4. Don't initialize with README"
    echo ""
    echo "5. Run these commands:"
    echo ""
    echo "   git remote add origin https://github.com/$GITHUB_USER/hermes-android-relay.git"
    echo "   git branch -M main"
    echo "   git push -u origin main"
    echo ""
fi

echo "=============================================="
echo "NEXT: Deploy to Render"
echo "=============================================="
echo ""
echo "Option A: Click deploy button"
echo "   https://render.com/deploy?repo=https://github.com/$GITHUB_USER/hermes-android-relay"
echo ""
echo "Option B: Use dashboard"
echo "   https://dashboard.render.com"
echo "   New → Web Service → Select GitHub repo"
echo ""
