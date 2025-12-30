#!/usr/bin/env python3
"""
Git Details Retriever and Auto-Commit/Push
Checks for git changes every 30 seconds and auto-commits/pushes
Uses OpenRouter LLM to generate intelligent commit messages
"""

import subprocess
import os
import sys
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def run_git_command(command):
    """Run a git command and return the output"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr.strip()}"


def generate_commit_message_with_llm(changed_files, diff_content):
    """Generate an intelligent commit message using OpenRouter LLM"""
    
    # Get OpenRouter API key from environment
    api_key = os.environ.get('OPENROUTER_API_KEY')
    
    if not api_key:
        print("⚠️  OPENROUTER_API_KEY not found in environment. Using default message.")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"Auto-commit: Updated files at {timestamp}"
    
    # Prepare the prompt
    file_list = "\n".join([f"- {f}" for f in changed_files])
    
    # Limit diff content to avoid token limits
    truncated_diff = diff_content[:3000] if len(diff_content) > 3000 else diff_content
    
    prompt = f"""You are a Git commit message expert. Generate a concise, conventional commit message based on the following changes.

Changed files:
{file_list}

Diff summary:
{truncated_diff}

Requirements:
- Use conventional commit format (e.g., feat:, fix:, docs:, refactor:, style:, test:, chore:)
- Keep it under 72 characters
- Be specific but concise
- Focus on WHAT changed and WHY, not HOW
- Use imperative mood (e.g., "Add feature" not "Added feature")

Generate ONLY the commit message, nothing else."""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com",
                "X-Title": "Git Auto-Commit Tool"
            },
            json={
                "model": "google/gemma-2-9b-it:free",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 100,
                "temperature": 0.7
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            commit_message = result['choices'][0]['message']['content'].strip()
            # Remove any quotes or extra formatting
            commit_message = commit_message.strip('"\'')
            print(f"🤖 LLM-generated commit message: {commit_message}")
            return commit_message
        else:
            print(f"⚠️  OpenRouter API error ({response.status_code}): {response.text}")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"Auto-commit: Updated files at {timestamp}"
            
    except Exception as e:
        print(f"⚠️  Error calling OpenRouter API: {e}")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"Auto-commit: Updated files at {timestamp}"


def get_git_details():
    """Retrieve various git details about the repository"""
    
    print("=" * 60)
    print("GIT REPOSITORY DETAILS")
    print("=" * 60)
    
    # Current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"\nDirectory: {current_dir}")
    
    # Check if it's a git repository
    is_git_repo = run_git_command("git rev-parse --is-inside-work-tree")
    if "Error" in is_git_repo or is_git_repo != "true":
        print("\n❌ This is not a git repository!")
        return
    
    print("\n✓ Valid Git Repository\n")
    
    # Current branch
    branch = run_git_command("git branch --show-current")
    print(f"Current Branch: {branch}")
    
    # Latest commit
    commit_hash = run_git_command("git rev-parse HEAD")
    print(f"Latest Commit Hash: {commit_hash}")
    
    # Commit message
    commit_message = run_git_command("git log -1 --pretty=%B")
    print(f"Latest Commit Message: {commit_message}")
    
    # Commit author and date
    commit_author = run_git_command("git log -1 --pretty=format:'%an <%ae>'")
    commit_date = run_git_command("git log -1 --pretty=format:'%ad'")
    print(f"Commit Author: {commit_author}")
    print(f"Commit Date: {commit_date}")
    
    # Remote URL
    remote_url = run_git_command("git config --get remote.origin.url")
    print(f"\nRemote Origin URL: {remote_url}")
    
    # Repository status
    print("\n" + "-" * 60)
    print("REPOSITORY STATUS")
    print("-" * 60)
    status = run_git_command("git status --short")
    if status:
        print(status)
    else:
        print("✓ Working tree clean")
    
    # Number of commits
    commit_count = run_git_command("git rev-list --count HEAD")
    print(f"\nTotal Commits: {commit_count}")
    
    # List of branches
    print("\n" + "-" * 60)
    print("LOCAL BRANCHES")
    print("-" * 60)
    branches = run_git_command("git branch")
    print(branches)
    
    # Recent commits (last 5)
    print("\n" + "-" * 60)
    print("RECENT COMMITS (Last 5)")
    print("-" * 60)
    recent_commits = run_git_command("git log -5 --oneline --decorate")
    print(recent_commits)
    
    print("\n" + "=" * 60)


def check_for_changes_and_commit(watch_path):
    """Check for git changes and commit/push if any exist"""
    try:
        # Change to the watch directory
        original_dir = os.getcwd()
        os.chdir(watch_path)
        
        # Check for changes
        status = run_git_command("git status --porcelain")
        
        if not status:
            print("✓ No changes detected", end="\r")
            os.chdir(original_dir)
            return False
        
        print("\n" + "🔄 " * 30)
        print("CHANGES DETECTED - AUTO-COMMITTING")
        print("🔄 " * 30)
        
        # Add all changes
        print("\n📦 Staging changes...")
        run_git_command("git add .")
        
        # Get list of changed files
        changed_files = run_git_command("git diff --cached --name-only")
        file_list = changed_files.split('\n') if changed_files else []
        
        print(f"📝 Changed files: {len(file_list)}")
        for file in file_list[:5]:  # Show first 5 files
            print(f"   - {file}")
        if len(file_list) > 5:
            print(f"   ... and {len(file_list) - 5} more")
        
        # Get diff for context
        full_diff = run_git_command("git diff --cached")
        
        # Use LLM to generate commit message
        print("\n🤖 Generating intelligent commit message...")
        commit_msg = generate_commit_message_with_llm(file_list, full_diff)
        
        # Commit
        print(f"\n💾 Committing: {commit_msg}")
        commit_result = run_git_command(f'git commit -m "{commit_msg}"')
        print(commit_result)
        
        # Push to remote
        print("\n🚀 Pushing to remote repository...")
        push_result = run_git_command("git push")
        
        if "Error" not in push_result:
            print("✅ Successfully pushed to remote!")
            if push_result:
                print(push_result)
        else:
            print(f"❌ Push failed: {push_result}")
        
        print("\n" + "🔄 " * 30)
        
        os.chdir(original_dir)
        return True
        
    except Exception as e:
        print(f"\n❌ Error during auto-commit: {e}")
        os.chdir(original_dir)
        return False


def start_auto_commit_watch(watch_path, check_interval=30):
    """Periodically check for changes and auto-commit/push"""
    print("\n" + "👁️ " * 30)
    print("STARTING AUTO-COMMIT MODE")
    print("👁️ " * 30)
    print(f"\nWatching directory: {watch_path}")
    print(f"Checking for changes every {check_interval} seconds...")
    print("\n⚠️  Press Ctrl+C to stop watching\n")
    
    check_count = 0
    
    try:
        while True:
            check_count += 1
            current_time = datetime.now().strftime("%H:%M:%S")
            print(f"[{current_time}] Check #{check_count}: ", end="", flush=True)
            
            changed = check_for_changes_and_commit(watch_path)
            
            if not changed:
                # Sleep for the check interval
                time.sleep(check_interval)
            else:
                # If we just committed, wait a bit before next check
                print(f"\n⏳ Waiting {check_interval} seconds before next check...")
                time.sleep(check_interval)
                
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping auto-commit watch...")
        print("✅ Auto-commit watch stopped")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Git details and auto-commit tool")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Enable auto-commit mode to periodically check for file changes"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to watch (defaults to current directory)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Check interval in seconds (default: 30)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.watch:
            watch_path = args.path or os.path.dirname(os.path.abspath(__file__))
            watch_path = os.path.abspath(watch_path)
            start_auto_commit_watch(watch_path, args.interval)
        else:
            get_git_details()
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
