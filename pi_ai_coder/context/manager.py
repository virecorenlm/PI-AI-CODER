#!/usr/bin/env python3
"""Smart context manager for the code assistant.

Handles file chunking, relevance scoring, and context window optimization.

This is the original ``context_manager.py`` moved into the ``pi_ai_coder``
package essentially unchanged -- behavior is preserved so existing context
selection/scoring keeps working the same way for both the CLI and the TUI.
"""

import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from dataclasses import dataclass


@dataclass
class FileChunk:
    """Represents a semantic chunk of a file"""
    path: str
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # 'function', 'class', 'import', 'full'
    relevance_score: float = 0.0

    def __len__(self):
        return len(self.content)

    def format_for_context(self) -> str:
        """Format chunk for model context"""
        return f"""File: {self.path} (lines {self.start_line}-{self.end_line})
```
{self.content}
```"""


class ContextManager:
    """Manages file context with intelligent chunking and prioritization"""

    # Token limits (conservative for 4K context models)
    MAX_CONTEXT_TOKENS = 3000  # Leave room for prompt + response
    AVG_CHARS_PER_TOKEN = 4
    MAX_CONTEXT_CHARS = MAX_CONTEXT_TOKENS * AVG_CHARS_PER_TOKEN

    # File patterns to ignore
    IGNORE_PATTERNS = {
        '*.pyc', '__pycache__', '.git', 'node_modules',
        '.venv', 'venv', '*.so', '*.o', '.DS_Store',
        '*.min.js', '*.min.css', 'package-lock.json'
    }

    def __init__(self, max_file_size_kb: int = 500, ignore_patterns: Optional[Iterable[str]] = None):
        self.max_file_size = max_file_size_kb * 1024
        self.file_cache: Dict[str, List[FileChunk]] = {}
        if ignore_patterns is not None:
            self.ignore_patterns = set(self.IGNORE_PATTERNS) | set(ignore_patterns)
        else:
            self.ignore_patterns = set(self.IGNORE_PATTERNS)

    def should_ignore(self, path: Path) -> bool:
        """Check if file should be ignored"""
        path_str = str(path)
        for pattern in self.ignore_patterns:
            if pattern.startswith('*'):
                if path_str.endswith(pattern[1:]):
                    return True
            elif pattern in path_str:
                return True
        return False

    def chunk_python_file(self, content: str, filepath: str) -> List[FileChunk]:
        """Chunk Python file by functions and classes"""
        chunks = []
        lines = content.split('\n')

        # Find all function and class definitions
        current_chunk = []
        current_start = 0
        current_type = 'code'
        indent_level = 0

        for i, line in enumerate(lines):
            # Detect function/class starts
            if re.match(r'^(def |class )', line):
                # Save previous chunk if exists
                if current_chunk:
                    chunks.append(FileChunk(
                        path=filepath,
                        content='\n'.join(current_chunk),
                        start_line=current_start,
                        end_line=i,
                        chunk_type=current_type
                    ))

                current_chunk = [line]
                current_start = i + 1
                current_type = 'function' if line.startswith('def ') else 'class'
                indent_level = len(line) - len(line.lstrip())

            # Continue collecting lines for current chunk
            elif current_chunk:
                line_indent = len(line) - len(line.lstrip()) if line.strip() else indent_level
                # If dedented or end of file, finish chunk
                if line.strip() and line_indent <= indent_level and i > current_start:
                    chunks.append(FileChunk(
                        path=filepath,
                        content='\n'.join(current_chunk),
                        start_line=current_start,
                        end_line=i,
                        chunk_type=current_type
                    ))
                    current_chunk = []
                    current_type = 'code'
                else:
                    current_chunk.append(line)
            else:
                current_chunk.append(line)

        # Add final chunk
        if current_chunk:
            chunks.append(FileChunk(
                path=filepath,
                content='\n'.join(current_chunk),
                start_line=current_start,
                end_line=len(lines),
                chunk_type=current_type
            ))

        return chunks if chunks else [FileChunk(
            path=filepath,
            content=content,
            start_line=1,
            end_line=len(lines),
            chunk_type='full'
        )]

    def chunk_generic_file(self, content: str, filepath: str, max_chunk_lines: int = 50) -> List[FileChunk]:
        """Chunk non-Python files by line count"""
        lines = content.split('\n')
        chunks = []

        for i in range(0, len(lines), max_chunk_lines):
            chunk_lines = lines[i:i + max_chunk_lines]
            chunks.append(FileChunk(
                path=filepath,
                content='\n'.join(chunk_lines),
                start_line=i + 1,
                end_line=min(i + max_chunk_lines, len(lines)),
                chunk_type='section'
            ))

        return chunks

    def load_file(self, filepath: str) -> List[FileChunk]:
        """Load and chunk a file"""
        path = Path(filepath)

        # Check cache
        if filepath in self.file_cache:
            return self.file_cache[filepath]

        # Ignore checks
        if self.should_ignore(path) or not path.exists() or not path.is_file():
            return []

        # Size check
        if path.stat().st_size > self.max_file_size:
            return []

        # Read file
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception:
            return []

        # Chunk based on file type
        if filepath.endswith('.py'):
            chunks = self.chunk_python_file(content, filepath)
        else:
            chunks = self.chunk_generic_file(content, filepath)

        # Cache it
        self.file_cache[filepath] = chunks
        return chunks

    def invalidate(self, filepath: Optional[str] = None) -> None:
        """Drop cached chunks, e.g. after a file changes on disk."""
        if filepath is None:
            self.file_cache.clear()
        else:
            self.file_cache.pop(filepath, None)

    def score_chunk_relevance(self, chunk: FileChunk, query: str) -> float:
        """Score how relevant a chunk is to the query"""
        query_lower = query.lower()
        content_lower = chunk.content.lower()

        score = 0.0

        # Keyword matching
        query_words = set(re.findall(r'\w+', query_lower))
        content_words = set(re.findall(r'\w+', content_lower))

        # Jaccard similarity
        if query_words:
            intersection = query_words & content_words
            union = query_words | content_words
            score += (len(intersection) / len(union)) * 10

        # Boost for function/class chunks (more meaningful)
        if chunk.chunk_type in ['function', 'class']:
            score += 2.0

        # Exact phrase matches
        for word in query_words:
            if word in content_lower:
                score += 1.0

        chunk.relevance_score = score
        return score

    def build_context(self, filepaths: List[str], query: str) -> str:
        """Build optimized context from files based on query"""
        all_chunks = []

        # Load and chunk all files
        for filepath in filepaths:
            chunks = self.load_file(filepath)
            for chunk in chunks:
                self.score_chunk_relevance(chunk, query)
            all_chunks.extend(chunks)

        # Sort by relevance
        all_chunks.sort(key=lambda c: c.relevance_score, reverse=True)

        # Build context staying within token limits
        context_parts = []
        total_chars = 0

        for chunk in all_chunks:
            chunk_size = len(chunk)
            if total_chars + chunk_size > self.MAX_CONTEXT_CHARS:
                break

            context_parts.append(chunk.format_for_context())
            total_chars += chunk_size

        return "\n\n".join(context_parts)

    def get_file_summary(self, filepath: str) -> str:
        """Get a quick summary of file structure"""
        chunks = self.load_file(filepath)

        summary_parts = [f"File: {filepath}"]

        for chunk in chunks:
            if chunk.chunk_type in ['function', 'class']:
                first_line = chunk.content.split('\n')[0]
                summary_parts.append(f"  {chunk.start_line}: {first_line[:80]}")

        return '\n'.join(summary_parts)

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """Rough token estimate for display purposes."""
        return len(text) // cls.AVG_CHARS_PER_TOKEN
