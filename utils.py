import os
import re
from pathlib import Path
from typing import List, Tuple
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def parse_github_url(url: str) -> Tuple[str, str]:
    """Extract owner and repo name from GitHub URL."""
    patterns = [
        r'github\.com[/:]([^/]+)/([^/\.]+)',
        r'([^/]+)/([^/]+)$'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            owner, repo = match.groups()
            repo = repo.replace('.git', '')
            return owner, repo
    
    raise ValueError(f"Invalid GitHub URL: {url}")


def create_output_dir(dir_name: str) -> Path:
    """Create output directory if it doesn't exist."""
    path = Path(dir_name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_repo_filename(owner: str, repo: str, suffix: str = "") -> str:
    """Generate filename for repository data."""
    base_name = f"{owner}_{repo}"
    if suffix:
        return f"{base_name}_{suffix}"
    return base_name


def split_into_chunks(items: List, chunk_size: int) -> List[List]:
    """Split a list into chunks of specified size."""
    chunks = []
    for i in range(0, len(items), chunk_size):
        chunks.append(items[i:i + chunk_size])
    return chunks


def format_datetime(dt_str: str) -> str:
    """Format ISO datetime string to readable format."""
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M')
    except:
        return dt_str


def clean_markdown_content(content: str) -> str:
    """Clean and escape content for markdown."""
    if not content:
        return ""
    
    # Remove excessive newlines
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    # Ensure code blocks are properly formatted
    content = re.sub(r'```(\w*)\n', r'```\1\n', content)
    
    return content.strip()


def estimate_tokens(text: str) -> int:
    """Rough estimate of token count for text."""
    # Rough approximation: 1 token ≈ 4 characters
    return len(text) // 4


def load_issue_files(repo_name: str, issues_dir: str = "issues") -> List[str]:
    """Load all issue markdown files for a repository."""
    issues_path = Path(issues_dir)
    if not issues_path.exists():
        raise FileNotFoundError(f"Issues directory not found: {issues_dir}")
    
    pattern = f"{repo_name}_issues_*.md"
    files = sorted(issues_path.glob(pattern))
    
    if not files:
        # Try without the _issues suffix
        pattern = f"{repo_name}_*.md"
        files = sorted(issues_path.glob(pattern))
    
    if not files:
        raise FileNotFoundError(f"No issue files found for repository: {repo_name}")
    
    contents = []
    for file in files:
        with open(file, 'r', encoding='utf-8') as f:
            contents.append(f.read())
    
    return contents


def create_progress_spinner(description: str) -> Progress:
    """Create a progress spinner for long-running operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True
    )


def print_success(message: str):
    """Print success message in green."""
    console.print(f"✅ {message}", style="green")


def print_error(message: str):
    """Print error message in red."""
    console.print(f"❌ {message}", style="red")


def print_info(message: str):
    """Print info message in blue."""
    console.print(f"ℹ️  {message}", style="blue")


def print_warning(message: str):
    """Print warning message in yellow."""
    console.print(f"⚠️  {message}", style="yellow")