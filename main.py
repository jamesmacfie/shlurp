#!/usr/bin/env python3

import os
import sys
from typing import Optional
import click
from dotenv import load_dotenv
from pathlib import Path

from github_scraper import GitHubScraper
from llm_summarizer import LLMSummarizer
from utils import (
    parse_github_url, get_repo_filename,
    print_success, print_error, print_info, print_warning
)

# Load environment variables
load_dotenv()


@click.group()
@click.version_option(version='1.0.0', prog_name='GitHub Issues Analyzer')
def cli():
    """GitHub Issues Scraper & Summarizer - Analyze repository issues with AI."""
    pass


@cli.command()
@click.argument('repo_url')
@click.option('--output-dir', '-o', default='results/issues', help='Output directory for issue files')
@click.option('--max-issues', '-m', type=int, help='Maximum number of issues to fetch')
@click.option('--max-per-file', type=int, default=50, help='Maximum issues per file')
@click.option('--no-comments', is_flag=True, help='Skip fetching comments')
@click.option('--token', help='GitHub personal access token (overrides env var)')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def fetch_issues(repo_url: str, output_dir: str, max_issues: Optional[int],
                max_per_file: int, no_comments: bool, token: Optional[str], verbose: bool):
    """Fetch GitHub issues and save to markdown files.
    
    REPO_URL: GitHub repository URL (e.g., https://github.com/owner/repo)
    """
    try:
        if verbose:
            print_info(f"Starting issue fetch for: {repo_url}")
        
        # Parse URL to validate
        owner, repo = parse_github_url(repo_url)
        
        # Get max issues per file from env if not specified
        if max_per_file == 50:
            max_per_file = int(os.getenv('MAX_ISSUES_PER_FILE', 50))
        
        # Create scraper and fetch issues
        try:
            scraper = GitHubScraper(github_token=token)
        except ValueError as e:
            print_error(str(e))
            sys.exit(1)
        
        saved_files = scraper.save_issues(
            repo_url,
            output_dir=output_dir,
            max_issues=max_issues,
            max_issues_per_file=max_per_file
        )
        
        if saved_files:
            print_success(f"Successfully saved {len(saved_files)} file(s)")
            if verbose:
                for file in saved_files:
                    print_info(f"  - {file}")
        else:
            print_warning("No issues were saved")
        
    except Exception as e:
        print_error(f"Failed to fetch issues: {e}")
        sys.exit(1)


@cli.command()
@click.argument('repo_name')
@click.option('--issues-dir', '-i', default='results/issues', help='Directory containing issue files')
@click.option('--output-dir', '-o', default='results/summaries', help='Output directory for summaries')
@click.option('--provider', type=click.Choice(['openai', 'anthropic']), help='LLM provider')
@click.option('--model', help='Specific model to use')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def summarize(repo_name: str, issues_dir: str, output_dir: str,
             provider: Optional[str], model: Optional[str], verbose: bool):
    """Summarize existing issue files using AI.
    
    REPO_NAME: Repository name (e.g., owner_repo or as saved in issue files)
    """
    try:
        if verbose:
            print_info(f"Starting summarization for: {repo_name}")
        
        # Create summarizer and generate summary
        summarizer = LLMSummarizer(provider=provider, model=model)
        summary_file = summarizer.summarize_repository(
            repo_name,
            issues_dir=issues_dir,
            output_dir=output_dir
        )
        
        print_success(f"Summary generated successfully")
        if verbose:
            print_info(f"Summary saved to: {summary_file}")
        
    except Exception as e:
        print_error(f"Failed to summarize issues: {e}")
        sys.exit(1)


@cli.command('fetch-and-summarize')
@click.argument('repo_url')
@click.option('--issues-dir', default='results/issues', help='Directory for issue files')
@click.option('--summaries-dir', default='results/summaries', help='Directory for summary files')
@click.option('--max-issues', '-m', type=int, help='Maximum number of issues to fetch')
@click.option('--max-per-file', type=int, default=50, help='Maximum issues per file')
@click.option('--provider', type=click.Choice(['openai', 'anthropic']), help='LLM provider')
@click.option('--model', help='Specific model to use')
@click.option('--token', help='GitHub personal access token')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def fetch_and_summarize(repo_url: str, issues_dir: str, summaries_dir: str,
                       max_issues: Optional[int], max_per_file: int,
                       provider: Optional[str], model: Optional[str],
                       token: Optional[str], verbose: bool):
    """Fetch GitHub issues and generate AI summary.
    
    REPO_URL: GitHub repository URL (e.g., https://github.com/owner/repo)
    """
    try:
        # Step 1: Fetch issues
        print_info("Step 1: Fetching issues...")
        
        owner, repo = parse_github_url(repo_url)
        repo_name = get_repo_filename(owner, repo)
        
        # Get max issues per file from env if not specified
        if max_per_file == 50:
            max_per_file = int(os.getenv('MAX_ISSUES_PER_FILE', 50))
        
        try:
            scraper = GitHubScraper(github_token=token)
        except ValueError as e:
            print_error(str(e))
            sys.exit(1)
        
        saved_files = scraper.save_issues(
            repo_url,
            output_dir=issues_dir,
            max_issues=max_issues,
            max_issues_per_file=max_per_file
        )
        
        if not saved_files:
            print_warning("No issues found. Exiting.")
            return
        
        print_success(f"Fetched and saved {len(saved_files)} file(s)")
        
        # Step 2: Generate summary
        print_info("\nStep 2: Generating AI summary...")
        
        summarizer = LLMSummarizer(provider=provider, model=model)
        summary_file = summarizer.summarize_repository(
            repo_name,
            issues_dir=issues_dir,
            output_dir=summaries_dir
        )
        
        print_success("\n✨ Process completed successfully!")
        print_info(f"Issues saved to: {issues_dir}/")
        print_info(f"Summary saved to: {summary_file}")
        
    except Exception as e:
        print_error(f"Process failed: {e}")
        sys.exit(1)



@cli.command()
def check_config():
    """Check configuration and API keys."""
    print_info("Checking configuration...\n")
    
    # Check GitHub token
    github_token = os.getenv('GITHUB_TOKEN')
    if github_token:
        print_success("✓ GitHub token configured")
    else:
        print_error("✗ GitHub token not found (REQUIRED)")
    
    # Check LLM configuration
    provider = os.getenv('LLM_PROVIDER', 'openai')
    print_info(f"LLM Provider: {provider}")
    
    if provider == 'openai':
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            print_success("✓ OpenAI API key configured")
        else:
            print_error("✗ OpenAI API key not found")
    elif provider == 'anthropic':
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            print_success("✓ Anthropic API key configured")
        else:
            print_error("✗ Anthropic API key not found")
    
    # Check other settings
    model = os.getenv('LLM_MODEL', 'default')
    max_issues = os.getenv('MAX_ISSUES_PER_FILE', '50')
    
    print_info(f"\nModel: {model}")
    print_info(f"Max issues per file: {max_issues}")
    
    # Check directories
    print_info("\nDefault directories:")
    print_info(f"  Issues: ./results/issues/")
    print_info(f"  Summaries: ./results/summaries/")


if __name__ == '__main__':
    cli()