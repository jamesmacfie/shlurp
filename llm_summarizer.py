import os
from typing import List, Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
import json

from utils import (
    load_issue_files, create_output_dir, get_repo_filename,
    estimate_tokens, create_progress_spinner,
    print_success, print_error, print_info, print_warning
)

load_dotenv()


class LLMSummarizer:
    """Summarize GitHub issues using LLMs."""
    
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or os.getenv('LLM_PROVIDER', 'openai')
        self.model = model
        self.client = None
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the LLM client based on provider."""
        if self.provider == 'openai':
            try:
                import openai
                api_key = os.getenv('OPENAI_API_KEY')
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not found in environment")
                
                self.client = openai.OpenAI(api_key=api_key)
                self.model = self.model or os.getenv('LLM_MODEL', 'gpt-4o-mini')
                print_info(f"Using OpenAI with model: {self.model}")
                
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")
        
        elif self.provider == 'anthropic':
            try:
                import anthropic
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not found in environment")
                
                self.client = anthropic.Anthropic(api_key=api_key)
                self.model = self.model or os.getenv('LLM_MODEL', 'claude-3-haiku-20240307')
                print_info(f"Using Anthropic with model: {self.model}")
                
            except ImportError:
                raise ImportError("Anthropic library not installed. Run: pip install anthropic")
        
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def _create_system_prompt(self) -> str:
        """Create the system prompt for issue summarization."""
        return """You are an expert at analyzing GitHub issues and providing actionable summaries.
        
Your task is to analyze the provided GitHub issues and create a comprehensive summary that includes:

1. **Overview**: Brief summary of the repository's issue landscape
2. **Priority Analysis**: Identify high-priority issues based on:
   - Number of comments/engagement
   - Labels (critical, bug, security, etc.)
   - Age of issues
   - User impact

4. **Common Themes**: Identify recurring problems or requests
5. **Recommendations**: Suggest actions for maintainers

Format your response in clear markdown with appropriate headers and bullet points.
Be concise but comprehensive. Focus on actionable insights."""
    
    def _create_user_prompt(self, issues_content: str, repo_info: str = "") -> str:
        """Create the user prompt with issue content."""
        prompt = f"Please analyze these GitHub issues{repo_info}:\n\n"
        prompt += "=" * 50 + "\n"
        prompt += issues_content
        prompt += "\n" + "=" * 50 + "\n\n"
        prompt += "Provide a comprehensive summary following the guidelines in your instructions."
        return prompt
    
    def _chunk_content(self, content: str, max_tokens: int = 100000) -> List[str]:
        """Split content into chunks that fit within token limits."""
        # Estimate tokens and split if needed
        estimated_tokens = estimate_tokens(content)
        
        if estimated_tokens <= max_tokens:
            return [content]
        
        # Split by issues (look for ## Issue # pattern)
        import re
        issues = re.split(r'(?=## Issue #\d+:)', content)
        issues = [i for i in issues if i.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for issue in issues:
            issue_tokens = estimate_tokens(issue)
            if current_size + issue_tokens > max_tokens and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [issue]
                current_size = issue_tokens
            else:
                current_chunk.append(issue)
                current_size += issue_tokens
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Make the actual LLM API call."""
        try:
            if self.provider == 'openai':
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=4000
                )
                return response.choices[0].message.content
            
            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.3,
                    max_tokens=4000
                )
                return response.content[0].text
            
        except Exception as e:
            print_error(f"LLM API error: {e}")
            raise
    
    def summarize_content(self, content: str, repo_info: str = "") -> str:
        """Summarize issue content using LLM."""
        system_prompt = self._create_system_prompt()
        chunks = self._chunk_content(content)
        
        if len(chunks) == 1:
            # Single chunk - direct summarization
            user_prompt = self._create_user_prompt(chunks[0], repo_info)
            return self._call_llm(system_prompt, user_prompt)
        
        else:
            # Multiple chunks - hierarchical summarization
            print_info(f"Content split into {len(chunks)} chunks for processing")
            
            chunk_summaries = []
            with create_progress_spinner("Summarizing chunks...") as progress:
                task = progress.add_task("Processing chunks...", total=len(chunks))
                
                for i, chunk in enumerate(chunks, 1):
                    user_prompt = self._create_user_prompt(
                        chunk, 
                        f" (Part {i}/{len(chunks)}{repo_info})"
                    )
                    summary = self._call_llm(system_prompt, user_prompt)
                    chunk_summaries.append(summary)
                    progress.update(task, advance=1)
            
            # Create final summary from chunk summaries
            print_info("Creating final summary from chunks...")
            combined_summaries = "\n\n---\n\n".join(chunk_summaries)
            
            final_prompt = f"""Please create a final, consolidated summary from these partial summaries of GitHub issues{repo_info}.
            
Combine the insights from all parts into a single, coherent summary following the same structure as before.
Eliminate any redundancy and provide the most important insights.

Partial Summaries:
{combined_summaries}"""
            
            return self._call_llm(system_prompt, final_prompt)
    
    def summarize_repository(self, repo_name: str, issues_dir: str = "issues",
                           output_dir: str = "summaries") -> str:
        """Load issue files and create summary."""
        # Parse repo name if it's in owner_repo format
        if '_' in repo_name:
            owner, repo = repo_name.split('_', 1)
            repo_info = f" for {owner}/{repo}"
        else:
            repo_info = f" for {repo_name}"
        
        print_info(f"Loading issue files for {repo_name}...")
        
        try:
            issue_contents = load_issue_files(repo_name, issues_dir)
        except FileNotFoundError as e:
            print_error(str(e))
            raise
        
        print_success(f"Loaded {len(issue_contents)} issue file(s)")
        
        # Combine all issue content
        combined_content = "\n\n".join(issue_contents)
        
        print_info("Generating summary with LLM...")
        summary = self.summarize_content(combined_content, repo_info)
        
        # Save summary
        output_path = create_output_dir(output_dir)
        filename = f"{repo_name}_summary.md"
        filepath = output_path / filename
        
        # Add metadata to summary
        final_content = f"# Summary of GitHub Issues{repo_info}\n\n"
        final_content += f"*Generated using {self.provider} ({self.model})*\n\n"
        final_content += "---\n\n"
        final_content += summary
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
        
        print_success(f"Summary saved to {filepath}")
        return str(filepath)