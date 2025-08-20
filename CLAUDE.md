# Shlurp

A Python CLI application that fetches GitHub repository issues, saves them to markdown files, and uses LLMs to generate summaries.

## Project Overview

This tool helps analyze GitHub repositories by:
1. Fetching all open issues from a GitHub repository
2. Extracting issue descriptions and comments
3. Handling pagination to get all issues
4. Saving issues to markdown files (with automatic splitting for large datasets)
5. Using LLMs to summarize the issues
6. Saving summaries to separate markdown files

## Setup

### Prerequisites
- Python 3.8+
- GitHub Personal Access Token (REQUIRED)
- OpenAI or Anthropic API key (for summarization)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

Required environment variables in `.env`:

```
# GitHub API (REQUIRED)
GITHUB_TOKEN=your_github_personal_access_token

# LLM API (choose one)
OPENAI_API_KEY=your_openai_api_key
# OR
ANTHROPIC_API_KEY=your_anthropic_api_key

# Configuration
LLM_PROVIDER=openai  # or 'anthropic'
LLM_MODEL=gpt-4o-mini  # or claude-3-haiku-20240307, etc.
MAX_ISSUES_PER_FILE=50  # Number of issues per markdown file
```

## Usage

### Fetch Issues Only
```bash
python main.py fetch-issues https://github.com/owner/repo
```

This will:
- Fetch all open issues from the repository
- Save them to `results/issues/owner_repo_issues_1.md`, `results/issues/owner_repo_issues_2.md`, etc.
- Split into multiple files if there are more than MAX_ISSUES_PER_FILE issues

### Summarize Existing Issues
```bash
python main.py summarize owner_repo
```

This will:
- Read all existing issue markdown files for the repository
- Send them to the configured LLM for summarization
- Save summaries to `results/summaries/owner_repo_summary.md`

### Fetch and Summarize (Complete Pipeline)
```bash
python main.py fetch-and-summarize https://github.com/owner/repo
```

This will:
- Fetch all open issues from the repository
- Save them to `results/issues/`
- Automatically generate an AI summary and save to `results/summaries/`

### Check Configuration
```bash
python main.py check-config
```

This will:
- Verify GitHub token is configured
- Check LLM provider and API keys
- Display current settings and default directories
- Validate environment configuration

### Additional Options

```bash
# Specify output directory for fetch-issues
python main.py fetch-issues https://github.com/owner/repo --output-dir ./my-issues

# Limit number of issues to fetch (for testing)
python main.py fetch-issues https://github.com/owner/repo --max-issues 10

# Skip fetching comments for faster processing
python main.py fetch-issues https://github.com/owner/repo --no-comments

# Specify GitHub token directly
python main.py fetch-issues https://github.com/owner/repo --token your_token_here

# Custom issues per file limit
python main.py fetch-issues https://github.com/owner/repo --max-per-file 25

# Fetch and summarize with specific LLM provider and model
python main.py fetch-and-summarize https://github.com/owner/repo --provider anthropic --model claude-3-haiku-20240307

# Specify custom directories for fetch-and-summarize
python main.py fetch-and-summarize https://github.com/owner/repo --issues-dir ./my-issues --summaries-dir ./my-summaries

# Summarize existing issues with specific model
python main.py summarize owner_repo --model gpt-4

# Verbose output
python main.py fetch-and-summarize https://github.com/owner/repo --verbose
```

## Output Structure

### Issues Markdown Format
Each issue is saved in the following format:

```markdown
## Issue #123: Issue Title

**Author:** username
**Created:** 2024-01-01
**Labels:** bug, enhancement

### Description
Issue description content...

### Comments

#### Comment by user1 (2024-01-02)
Comment content...

#### Comment by user2 (2024-01-03)
Another comment...

---
```

### Summary Format
Summaries include:
- Overall repository health assessment
- Most common issue categories
- Critical issues requiring attention
- Trends and patterns
- Recommended actions


## Advanced Features

### Smart Progress Tracking
- Real-time progress bars using Rich library
- Colored output for better readability
- Detailed status updates during processing

### Robust Error Handling
- **Automatic retry logic** with exponential backoff using Tenacity
- **Rate limit detection** and automatic waiting for GitHub API
- **Network error recovery** with intelligent retries
- **Graceful degradation** when optional features fail (like comments)

### Intelligent Content Processing
- **Pull request filtering** - Automatically excludes PRs from issue lists
- **Hierarchical summarization** - For large datasets, creates chunk summaries then final summary
- **Token estimation** - Smart content splitting to respect LLM context limits
- **File pattern matching** - Flexible loading of existing issue files

### GitHub API Integration
- **Comprehensive issue fetching** with full metadata
- **Comment retrieval** with author and timestamp information
- **Pagination handling** for repositories with many issues
- **Markdown content cleaning** for better processing

## Notes for Development

### Dependencies
The project uses several key libraries:
- `requests` - HTTP requests to GitHub API
- `click` - Command-line interface framework
- `python-dotenv` - Environment variable management
- `openai` / `anthropic` - LLM API clients
- `tenacity` - Retry logic with exponential backoff
- `rich` - Progress bars and colored terminal output
- `beautifulsoup4` - HTML parsing (if needed)

### Rate Limiting
- GitHub API has rate limits (5000 requests/hour with token)
- The tool implements automatic rate limit handling with retries
- GITHUB_TOKEN is required for all operations

### Large Repositories
- For repos with many issues, files are automatically split
- Each file contains MAX_ISSUES_PER_FILE issues (default: 50)
- Summaries process all files for a repository

### LLM Context Limits
- Large issue sets are automatically chunked for LLM processing
- Summaries are hierarchical (chunk summaries → final summary) for very large datasets
- Token estimation ensures content fits within model limits