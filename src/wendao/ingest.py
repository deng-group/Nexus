"""Extract course notes (Markdown/MyST pages and Jupyter notebooks) into search chunks.

Each file is split into chunks of roughly 100-400 tokens, keeping paragraphs together.
Every chunk records its file, chapter (top-level folder), section, title, and headings.
Files listed as time-sensitive (by default `syllabus.md` and `calendar.md`) are tagged
with the course term so answers about deadlines and schedules state which term they mean.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

import nbformat


class ContentExtractor:
    """Extract content from MyST markdown and Jupyter notebook files"""

    def __init__(self, repo_path: str | Path, time_sensitive_files: List[str] | None = None, term: str = ""):
        self.repo_path = Path(repo_path)
        self.time_sensitive_files = set(time_sensitive_files if time_sensitive_files is not None else ["syllabus.md", "calendar.md"])
        self.chunks = []
        self.course_temporal_context = self.load_course_temporal_context(term)

    def load_course_temporal_context(self, term: str = "") -> Dict[str, Any]:
        """Use the configured term, or read it from a `- Year: ...` line in syllabus.md."""
        syllabus_path = self.repo_path / "syllabus.md"
        context = {
            "source": "wendao.toml" if term else "syllabus.md",
            "year": None,
            "academic_year": None,
            "semester": None,
            "requires_time_disambiguation": True,
        }

        year = term.strip()
        if not year and syllabus_path.exists():
            content = syllabus_path.read_text(encoding="utf-8")
            match = re.search(r"^- Year:\s*(.+)$", content, re.MULTILINE)
            if match:
                year = match.group(1).strip()
        if not year:
            return context

        context["year"] = year

        ay_match = re.search(r"(AY\d{4}/\d{4})", year)
        semester_match = re.search(r"(Semester\s+\d+)", year, re.IGNORECASE)
        if ay_match:
            context["academic_year"] = ay_match.group(1)
        if semester_match:
            context["semester"] = semester_match.group(1)

        return context

    def extract_headings(self, content: str) -> List[Dict[str, Any]]:
        """Extract headings hierarchy from markdown content"""
        headings = []
        for match in re.finditer(r'^(#{1,6})\s+(.+)$', content, re.MULTILINE):
            level = len(match.group(1))
            title = match.group(2).strip()
            headings.append({
                'level': level,
                'title': title,
                'position': match.start()
            })
        return headings

    def make_chunk(self, content: str, token_estimate: float, metadata: Dict[str, Any], chunk_id: int) -> Dict[str, Any]:
        """Create one chunk and inject temporal context where needed."""
        chunk_content = content.strip()
        if metadata.get("temporal_context"):
            note = metadata.get("temporal_context_note", "")
            if note and not chunk_content.startswith(note):
                chunk_content = f"{note}\n\n{chunk_content}"

        return {
            'chunk_id': f"{metadata['file_path']}_{chunk_id}",
            'content': chunk_content,
            'token_estimate': int(token_estimate),
            **metadata
        }

    def split_into_chunks(self, content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split content into chunks of 100-300 tokens (approximately 200-600 words)
        while preserving paragraph boundaries
        """
        chunks = []

        # Split by headings first to preserve context
        sections = re.split(r'\n(?=#{1,6}\s+)', content)

        current_chunk = ""
        current_tokens = 0
        chunk_id = 0

        # Approximate tokens: 1 token ≈ 0.75 words
        TARGET_TOKENS = 200
        MAX_TOKENS = 400
        MIN_TOKENS = 100

        for section in sections:
            if not section.strip():
                continue

            # Split section into paragraphs
            paragraphs = section.split('\n\n')

            for para in paragraphs:
                if not para.strip():
                    continue

                # Estimate tokens (rough approximation)
                para_tokens = len(para.split()) * 1.33

                # If paragraph is too large, split it
                if para_tokens > MAX_TOKENS:
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    for sent in sentences:
                        sent_tokens = len(sent.split()) * 1.33
                        if current_tokens + sent_tokens > MAX_TOKENS and current_tokens > MIN_TOKENS:
                            # Save current chunk
                            chunk_data = self.make_chunk(current_chunk, current_tokens, metadata, chunk_id)
                            chunks.append(chunk_data)
                            chunk_id += 1
                            current_chunk = sent
                            current_tokens = sent_tokens
                        else:
                            current_chunk += " " + sent
                            current_tokens += sent_tokens
                else:
                    # Add paragraph to current chunk
                    if current_tokens + para_tokens > MAX_TOKENS and current_tokens > MIN_TOKENS:
                        # Save current chunk
                        chunk_data = self.make_chunk(current_chunk, current_tokens, metadata, chunk_id)
                        chunks.append(chunk_data)
                        chunk_id += 1
                        current_chunk = para
                        current_tokens = para_tokens
                    else:
                        if current_chunk:
                            current_chunk += "\n\n" + para
                        else:
                            current_chunk = para
                        current_tokens += para_tokens

        # Save remaining content
        if current_chunk.strip():
            chunk_data = self.make_chunk(current_chunk, current_tokens, metadata, chunk_id)
            chunks.append(chunk_data)

        return chunks

    def temporal_metadata_for_file(self, relative_path: str) -> Dict[str, Any]:
        """Return additional time-sensitive metadata for offering-specific files."""
        if relative_path not in self.time_sensitive_files:
            return {}

        year = self.course_temporal_context.get("year") or "unknown academic year/semester"
        kind = Path(relative_path).stem.replace("_", " ")
        note = (
            f"Temporal context: This {kind} information applies to {year}. "
            "Answers about course schedule, assessment, grading, deadlines, or logistics must state this time context."
        )

        return {
            "temporal_context": self.course_temporal_context,
            "temporal_context_note": note,
            "time_sensitive": True,
        }

    def extract_markdown(self, file_path: Path, module: str, section: str) -> List[Dict[str, Any]]:
        """Extract content from markdown file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract headings
        headings = self.extract_headings(content)

        # Extract metadata
        metadata = {
            'file_path': str(file_path.relative_to(self.repo_path)),
            'file_type': 'markdown',
            'module': module,
            'section': section,
            'headings': headings,
            'title': headings[0]['title'] if headings else file_path.stem,
            'concepts': self.extract_concepts(content),
            'code_blocks': self.extract_code_blocks(content)
        }
        metadata.update(self.temporal_metadata_for_file(metadata['file_path']))

        # Split into chunks
        chunks = self.split_into_chunks(content, metadata)
        return chunks

    def extract_notebook(self, file_path: Path, module: str, section: str) -> List[Dict[str, Any]]:
        """Extract content from Jupyter notebook"""
        with open(file_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)

        content_parts = []
        code_cells = []

        for cell in nb.cells:
            if cell.cell_type == 'markdown':
                content_parts.append(cell.source)
            elif cell.cell_type == 'code':
                if cell.source.strip():
                    code_cells.append(cell.source)
                    # Also include code descriptions
                    content_parts.append(f"```python\n{cell.source}\n```")

        full_content = "\n\n".join(content_parts)

        # Extract headings
        headings = self.extract_headings(full_content)

        metadata = {
            'file_path': str(file_path.relative_to(self.repo_path)),
            'file_type': 'notebook',
            'module': module,
            'section': section,
            'headings': headings,
            'title': headings[0]['title'] if headings else file_path.stem,
            'concepts': self.extract_concepts(full_content),
            'code_blocks': code_cells
        }
        metadata.update(self.temporal_metadata_for_file(metadata['file_path']))

        chunks = self.split_into_chunks(full_content, metadata)
        return chunks

    def extract_concepts(self, content: str) -> List[str]:
        """Extract key concepts from content using various patterns"""
        concepts = []

        # Extract from bold text
        bold_matches = re.findall(r'\*\*([^*]+)\*\*', content)
        concepts.extend(bold_matches)

        # Extract from definitions/admonitions
        admonition_matches = re.findall(r'```{admonition}.*?:class:\s*\w+\s*\n(.+?)```', content, re.DOTALL)
        for match in admonition_matches:
            # Extract first line as concept
            lines = match.strip().split('\n')
            if lines:
                concepts.append(lines[0].strip())

        # Extract from inline code (often used for technical terms)
        code_matches = re.findall(r'`([^`]+)`', content)
        concepts.extend([m for m in code_matches if len(m.split()) <= 3])  # Short technical terms

        # Deduplicate and filter
        seen = set()
        unique_concepts = []
        for concept in concepts:
            concept = concept.strip()
            if concept and len(concept) > 2 and concept not in seen:
                seen.add(concept)
                unique_concepts.append(concept)

        return unique_concepts[:20]  # Limit to top 20 concepts

    def extract_code_blocks(self, content: str) -> List[str]:
        """Extract code blocks from content"""
        code_blocks = re.findall(r'```(?:python|py)?\n(.*?)```', content, re.DOTALL)
        return [block.strip() for block in code_blocks if block.strip()]

    def process_all(self, toc_structure: Dict[str, Any]) -> None:
        """Process all files according to TOC structure"""
        for item in toc_structure:
            if 'file' in item:
                file_path = self.repo_path / item['file']

                if not file_path.exists():
                    print(f"Warning: {file_path} does not exist")
                    continue

                # Determine module and section from file path
                parts = file_path.relative_to(self.repo_path).parts
                module = parts[0] if len(parts) > 1 else "root"
                section = parts[1] if len(parts) > 2 else file_path.stem

                if file_path.suffix == '.md':
                    chunks = self.extract_markdown(file_path, module, section)
                    self.chunks.extend(chunks)
                elif file_path.suffix == '.ipynb':
                    chunks = self.extract_notebook(file_path, module, section)
                    self.chunks.extend(chunks)

            if 'children' in item:
                self.process_all(item['children'])

    def process_file(self, relative_path: str) -> None:
        """Process one markdown or notebook file by relative path."""
        file_path = self.repo_path / relative_path

        if not file_path.exists():
            print(f"Warning: {file_path} does not exist")
            return

        if file_path.suffix not in {'.md', '.ipynb'}:
            return

        parts = file_path.relative_to(self.repo_path).parts
        module = parts[0] if len(parts) > 1 else "root"
        section = parts[1] if len(parts) > 2 else file_path.stem

        if file_path.suffix == '.md':
            chunks = self.extract_markdown(file_path, module, section)
        else:
            chunks = self.extract_notebook(file_path, module, section)

        self.chunks.extend(chunks)

    def process_files(self, relative_paths: List[str]) -> None:
        """Process a list of relative file paths."""
        for relative_path in relative_paths:
            self.process_file(relative_path)

    def save_chunks(self, output_path: str | Path) -> None:
        """Save chunks to a JSONL file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            for chunk in self.chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + '\n')


def load_toc_structure(repo_path: str | Path) -> Dict[str, Any]:
    """Load the table of contents from myst.yml."""
    import yaml

    myst_config = Path(repo_path) / 'myst.yml'
    with open(myst_config, 'r') as f:
        config = yaml.safe_load(f)

    return config['project']['toc']


def discover_content_files(repo_path: str | Path, exclude: List[str], ignore_dirs: List[str]) -> List[str]:
    """Find every Markdown and notebook file, skipping ignored folders and excluded files."""
    repo = Path(repo_path)
    ignored_parts = set(ignore_dirs)
    excluded = {str(Path(item)) for item in exclude}
    files = []

    for path in repo.rglob('*'):
        if not path.is_file():
            continue
        if path.suffix not in {'.md', '.ipynb'}:
            continue
        relative = path.relative_to(repo)
        if any(part in ignored_parts or part.endswith('.egg-info') for part in relative.parts[:-1]):
            continue
        relative_str = str(relative)
        if relative_str in excluded:
            continue
        files.append(relative_str)

    return sorted(files)


def extract(workspace) -> dict:
    """Extract the workspace's course notes into build/chunks.jsonl. Returns a short summary."""
    source = workspace.require_source()
    extractor = ContentExtractor(source, workspace.time_sensitive_files, workspace.term)
    if workspace.use_toc:
        extractor.process_all(load_toc_structure(source))
        file_count = len({chunk["file_path"] for chunk in extractor.chunks})
    else:
        files = discover_content_files(source, workspace.exclude, workspace.ignore_dirs)
        extractor.process_files(files)
        file_count = len(files)
    extractor.save_chunks(workspace.chunks_path)
    return {"files": file_count, "chunks": len(extractor.chunks), "term": extractor.course_temporal_context.get("year")}
