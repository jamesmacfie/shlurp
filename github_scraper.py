import os
import time
from typing import List, Dict, Optional, Any
from pathlib import Path
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

from utils import (
    parse_github_url, create_output_dir, get_repo_filename,
    split_into_chunks, format_datetime, clean_markdown_content,
    create_progress_spinner, print_success, print_error, print_info, print_warning
)

load_dotenv()


class GitHubScraper:
    """Scrape GitHub issues and comments."""
    
    def __init__(self, github_token: Optional[str] = None):
        self.session = requests.Session()
        self.base_url = "https://api.github.com"
        
        # Use token from parameter or environment
        token = github_token or os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError(
                "GitHub token is required. Please provide it via --token parameter "
                "or set GITHUB_TOKEN environment variable."
            )
        
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        })
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _make_request(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """Make API request with retry logic."""
        response = self.session.get(url, params=params)
        
        if response.status_code == 403:
            # Check for rate limiting
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining == 0:
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    sleep_time = reset_time - int(time.time()) + 1
                    if sleep_time > 0:
                        print_warning(f"Rate limit hit. Waiting {sleep_time} seconds...")
                        time.sleep(sleep_time)
                        return self._make_request(url, params)
        
        response.raise_for_status()
        return response
    
    def fetch_issues(self, owner: str, repo: str, max_issues: Optional[int] = None) -> List[Dict]:
        """Fetch all open issues from a repository."""
        issues = []
        page = 1
        per_page = 100
        
        with create_progress_spinner("Fetching issues...") as progress:
            task = progress.add_task("Fetching issues...", total=None)
            
            while True:
                url = f"{self.base_url}/repos/{owner}/{repo}/issues"
                params = {
                    'state': 'open',
                    'page': page,
                    'per_page': per_page,
                    'sort': 'created',
                    'direction': 'desc'
                }
                
                try:
                    response = self._make_request(url, params)
                    page_issues = response.json()
                    
                    if not page_issues:
                        break
                    
                    # Filter out pull requests (they appear as issues in the API)
                    page_issues = [issue for issue in page_issues if 'pull_request' not in issue]
                    
                    issues.extend(page_issues)
                    progress.update(task, description=f"Fetched {len(issues)} issues...")
                    
                    if max_issues and len(issues) >= max_issues:
                        issues = issues[:max_issues]
                        break
                    
                    # Check if there are more pages
                    if 'Link' in response.headers:
                        if 'rel="next"' not in response.headers['Link']:
                            break
                    else:
                        if len(page_issues) < per_page:
                            break
                    
                    page += 1
                    
                except requests.exceptions.RequestException as e:
                    print_error(f"Error fetching issues: {e}")
                    break
        
        return issues
    
    def fetch_comments(self, owner: str, repo: str, issue_number: int) -> List[Dict]:
        """Fetch all comments for a specific issue."""
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/comments"
        
        try:
            response = self._make_request(url)
            return response.json()
        except requests.exceptions.RequestException as e:
            print_warning(f"Error fetching comments for issue #{issue_number}: {e}")
            return []
    
    def issues_to_markdown(self, issues: List[Dict], owner: str, repo: str, 
                          fetch_comments: bool = True) -> str:
        """Convert issues to markdown format."""
        markdown_parts = [f"# GitHub Issues for {owner}/{repo}\n\n"]
        markdown_parts.append(f"*Generated on {format_datetime(time.strftime('%Y-%m-%dT%H:%M:%SZ'))}*\n\n")
        markdown_parts.append(f"**Total Open Issues:** {len(issues)}\n\n")
        markdown_parts.append("---\n\n")
        
        with create_progress_spinner("Processing issues...") as progress:
            task = progress.add_task("Processing issues...", total=len(issues))
            
            for issue in issues:
                # Issue header
                markdown_parts.append(f"## Issue #{issue['number']}: {issue['title']}\n\n")
                
                # Metadata
                markdown_parts.append(f"**Author:** {issue['user']['login']}\n")
                markdown_parts.append(f"**Created:** {format_datetime(issue['created_at'])}\n")
                
                if issue.get('updated_at'):
                    markdown_parts.append(f"**Updated:** {format_datetime(issue['updated_at'])}\n")
                
                if issue.get('labels'):
                    labels = ', '.join([label['name'] for label in issue['labels']])
                    markdown_parts.append(f"**Labels:** {labels}\n")
                
                if issue.get('assignees'):
                    assignees = ', '.join([a['login'] for a in issue['assignees']])
                    markdown_parts.append(f"**Assignees:** {assignees}\n")
                
                markdown_parts.append("\n")
                
                # Issue description
                markdown_parts.append("### Description\n\n")
                description = clean_markdown_content(issue.get('body', 'No description provided.'))
                markdown_parts.append(f"{description}\n\n")
                
                # Fetch and add comments
                if fetch_comments and issue.get('comments', 0) > 0:
                    comments = self.fetch_comments(owner, repo, issue['number'])
                    if comments:
                        markdown_parts.append("### Comments\n\n")
                        for comment in comments:
                            author = comment['user']['login']
                            created = format_datetime(comment['created_at'])
                            body = clean_markdown_content(comment.get('body', ''))
                            
                            markdown_parts.append(f"#### Comment by {author} ({created})\n\n")
                            markdown_parts.append(f"{body}\n\n")
                
                markdown_parts.append("---\n\n")
                progress.update(task, advance=1)
        
        return ''.join(markdown_parts)
    
    def save_issues(self, url: str, output_dir: str = "issues", 
                   max_issues: Optional[int] = None,
                   max_issues_per_file: int = 50) -> List[str]:
        """Fetch and save issues to markdown files."""
        owner, repo = parse_github_url(url)
        
        print_info(f"Fetching issues from {owner}/{repo}...")
        issues = self.fetch_issues(owner, repo, max_issues)
        
        if not issues:
            print_warning("No open issues found.")
            return []
        
        print_success(f"Found {len(issues)} open issues")
        
        # Create output directory
        output_path = create_output_dir(output_dir)
        
        # Split issues into chunks if necessary
        chunks = split_into_chunks(issues, max_issues_per_file)
        saved_files = []
        
        for i, chunk in enumerate(chunks, 1):
            # Generate markdown
            markdown_content = self.issues_to_markdown(chunk, owner, repo)
            
            # Save to file
            if len(chunks) > 1:
                filename = f"{get_repo_filename(owner, repo, f'issues_{i}')}.md"
            else:
                filename = f"{get_repo_filename(owner, repo, 'issues')}.md"
            
            filepath = output_path / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            saved_files.append(str(filepath))
            print_success(f"Saved {len(chunk)} issues to {filepath}")
        
        return saved_files