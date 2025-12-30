#!/usr/bin/env python3
"""
Git Details Retriever and Auto-Commit/Push
Retrieves git information and monitors for file changes to auto-commit and push
Uses OpenRouter LLM to generate intelligent commit messages
"""

import subprocess
import os
import sys
import time
import json
import requests
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


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


class GitAutoCommitHandler(FileSystemEventHandler):
    """Handler for file system events that auto-commits and pushes changes"""
    
    def __init__(self, watch_path):
        self.watch_path = watch_path
        self.last_commit_time = 0
        self.debounce_seconds = 5  # Wait 5 seconds before committing
        self.pending_changes = False
        
    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Ignore git internal files and this script itself
        if '.git' in event.src_path or event.src_path.endswith('git_details.py'):
            return
            
        print(f"\n📝 File changed: {event.src_path}")
        self.pending_changes = True
        self.schedule_commit()
    
    def on_created(self, event):
        if event.is_directory:
            return
            
        if '.git' in event.src_path or event.src_path.endswith('git_details.py'):
            return
            
        print(f"\n➕ File created: {event.src_path}")
        self.pending_changes = True
        self.schedule_commit()
    
    def on_deleted(self, event):
        if event.is_directory:
            return
            
        if '.git' in event.src_path or event.src_path.endswith('git_details.py'):
            return
            
        print(f"\n🗑️  File deleted: {event.src_path}")
        self.pending_changes = True
        self.schedule_commit()
    
    def schedule_commit(self):
        """Schedule a commit after debounce period"""
        self.last_commit_time = time.time()
        
    def check_and_commit(self):
        """Check if it's time to commit and push"""
        if not self.pending_changes:
            return
            
        if time.time() - self.last_commit_time < self.debounce_seconds:
            return
        
        self.pending_changes = False
        self.auto_commit_and_push()
    
    def auto_commit_and_push(self):
        """Automatically commit and push changes"""
        try:
            # Check for changes
            status = run_git_command("git status --porcelain")
            if not status:
                print("ℹ️  No changes to commit")
                return
            
            print("\n" + "🔄 " * 30)
            print("AUTO-COMMITTING CHANGES")
            print("🔄 " * 30)
            
            # Add all changes
            print("\n📦 Staging changes...")
            run_git_command("git add .")
            
            # Get list of changed files
            changed_files = run_git_command("git diff --cached --name-only")
            file_list = changed_files.split('\n') if changed_files else []
            
            # Get diff for context
            diff_content = run_git_command("git diff --cached --stat")
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
                print(push_result)
            else:
                print(f"❌ Push failed: {push_result}")
            
            print("\n" + "🔄 " * 30)
            
        except Exception as e:
            print(f"❌ Error during auto-commit: {e}")


def start_auto_commit_watch(watch_path):
    """Start watching directory for changes and auto-commit"""
    print("\n" + "👁️ " * 30)
    print("STARTING AUTO-COMMIT MODE")
    print("👁️ " * 30)
    print(f"\nWatching directory: {watch_path}")
    print("Monitoring for file changes...")
    print("\n⚠️  Press Ctrl+C to stop watching\n")
    
    event_handler = GitAutoCommitHandler(watch_path)
    observer = Observer()
    observer.schedule(event_handler, watch_path, recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
            event_handler.check_and_commit()
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping auto-commit watch...")
        observer.stop()
    
    observer.join()
    print("✅ Auto-commit watch stopped")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Git details and auto-commit tool")
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Enable auto-commit mode to watch for file changes"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to watch (defaults to current directory)"
    )
    
    args = parser.parse_args()
    
    try:
        if args.watch:
            watch_path = args.path or os.path.dirname(os.path.abspath(__file__))
            start_auto_commit_watch(watch_path)
        else:
            get_git_details()
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
