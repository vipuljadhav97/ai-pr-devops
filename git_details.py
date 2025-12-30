#!/usr/bin/env python3
"""
Git Details Retriever and Auto-Commit/Push
Retrieves git information and monitors for file changes to auto-commit and push
"""

import subprocess
import os
import sys
import time
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
            
            # Generate commit message
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Get list of changed files
            changed_files = run_git_command("git diff --cached --name-only")
            file_list = changed_files.split('\n') if changed_files else []
            
            if len(file_list) == 1:
                commit_msg = f"Auto-commit: Updated {file_list[0]} at {timestamp}"
            else:
                commit_msg = f"Auto-commit: Updated {len(file_list)} files at {timestamp}"
            
            # Commit
            print(f"💾 Committing: {commit_msg}")
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
