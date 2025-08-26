"""
Duplicate Code Detection Analyzer

Detects exact and similar code duplicates across the codebase.
"""

import ast
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
import difflib

from migration_assistant.checkup.analyzers.base import BaseAnalyzer
from migration_assistant.checkup.models import (
    Duplicate, IssueType, IssueSeverity, CheckupConfig
)


class CodeBlock:
    """Represents a block of code for duplicate detection."""
    
    def __init__(
        self,
        file_path: Path,
        start_line: int,
        end_line: int,
        content: str,
        content_hash: str,
        block_type: str = "generic"
    ):
        self.file_path = file_path
        self.start_line = start_line
        self.end_line = end_line
        self.content = content
        self.content_hash = content_hash
        self.block_type = block_type
        self.lines_of_code = end_line - start_line + 1
    
    def __eq__(self, other):
        return isinstance(other, CodeBlock) and self.content_hash == other.content_hash
    
    def __hash__(self):
        return hash(self.content_hash)
    
    def __repr__(self):
        return f"CodeBlock({self.file_path}:{self.start_line}-{self.end_line})"


class DuplicateGroup:
    """Group of duplicate code blocks."""
    
    def __init__(self, blocks: List[CodeBlock], similarity_score: float = 1.0):
        self.blocks = blocks
        self.similarity_score = similarity_score
        self.total_lines = sum(block.lines_of_code for block in blocks)
        self.duplicate_count = len(blocks)
    
    @property
    def representative_block(self) -> CodeBlock:
        """Get the representative block (first one)."""
        return self.blocks[0] if self.blocks else None
    
    @property
    def duplicate_files(self) -> List[Path]:
        """Get list of files containing duplicates."""
        return [block.file_path for block in self.blocks]


class DuplicateCodeDetector(BaseAnalyzer):
    """Analyzer for detecting duplicate and similar code blocks."""
    
    def __init__(self, config: CheckupConfig):
        super().__init__(config)
        self.min_lines = config.min_duplicate_lines
        self.similarity_threshold = config.similarity_threshold
        self._file_contents: Dict[Path, str] = {}
        self._file_lines: Dict[Path, List[str]] = {}
        self._code_blocks: List[CodeBlock] = []
    
    def get_supported_file_types(self) -> List[str]:
        """Return supported file types."""
        return ['.py']
    
    async def analyze(self) -> List[Duplicate]:
        """
        Analyze codebase for duplicate code.
        
        Returns:
            List of duplicate code issues
        """
        await self.pre_analyze()
        
        # Load all file contents
        await self._load_file_contents()
        
        # Extract code blocks
        await self._extract_code_blocks()
        
        # Find exact duplicates
        exact_duplicates = await self._find_exact_duplicates()
        
        # Find similar code blocks
        similar_duplicates = await self._find_similar_duplicates()
        
        # Combine and create issues
        all_duplicates = exact_duplicates + similar_duplicates
        issues = await self._create_duplicate_issues(all_duplicates)
        
        # Update metrics
        self.update_metrics(
            duplicate_blocks=len(all_duplicates),
            duplicate_lines=sum(group.total_lines for group in all_duplicates)
        )
        
        await self.post_analyze(issues)
        return issues
    
    async def _load_file_contents(self) -> None:
        """Load contents of all Python files."""
        python_files = self.get_python_files()
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self._file_contents[file_path] = content
                    self._file_lines[file_path] = content.splitlines()
            except (UnicodeDecodeError, IOError) as e:
                # Skip files that can't be read
                continue
    
    async def _extract_code_blocks(self) -> None:
        """Extract code blocks from all files."""
        for file_path, content in self._file_contents.items():
            try:
                # Parse AST to extract functions and classes
                tree = ast.parse(content)
                await self._extract_ast_blocks(file_path, tree)
                
                # Extract line-based blocks for exact matching
                await self._extract_line_blocks(file_path)
                
            except SyntaxError:
                # Skip files with syntax errors
                continue
    
    async def _extract_ast_blocks(self, file_path: Path, tree: ast.AST) -> None:
        """Extract function and class blocks from AST."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start_line = node.lineno
                end_line = getattr(node, 'end_lineno', start_line)
                
                if end_line - start_line + 1 >= self.min_lines:
                    lines = self._file_lines[file_path][start_line-1:end_line]
                    content = '\n'.join(lines)
                    content_hash = self._hash_content(content)
                    
                    block_type = "function" if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "class"
                    
                    block = CodeBlock(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        content=content,
                        content_hash=content_hash,
                        block_type=block_type
                    )
                    self._code_blocks.append(block)
    
    async def _extract_line_blocks(self, file_path: Path) -> None:
        """Extract sliding window blocks of lines."""
        lines = self._file_lines[file_path]
        
        # Create sliding window blocks
        for start_idx in range(len(lines) - self.min_lines + 1):
            end_idx = start_idx + self.min_lines
            
            # Skip blocks that are mostly whitespace or comments
            block_lines = lines[start_idx:end_idx]
            if self._is_meaningful_block(block_lines):
                content = '\n'.join(block_lines)
                content_hash = self._hash_content(content)
                
                block = CodeBlock(
                    file_path=file_path,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    content=content,
                    content_hash=content_hash,
                    block_type="lines"
                )
                self._code_blocks.append(block)
    
    def _is_meaningful_block(self, lines: List[str]) -> bool:
        """Check if a block of lines contains meaningful code."""
        meaningful_lines = 0
        
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and stripped != '':
                meaningful_lines += 1
        
        # At least 50% of lines should be meaningful
        return meaningful_lines >= len(lines) * 0.5
    
    def _hash_content(self, content: str) -> str:
        """Create hash of normalized content."""
        # Normalize content by removing extra whitespace
        normalized = '\n'.join(line.strip() for line in content.splitlines() if line.strip())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    async def _find_exact_duplicates(self) -> List[DuplicateGroup]:
        """Find exact duplicate code blocks."""
        hash_groups: Dict[str, List[CodeBlock]] = defaultdict(list)
        
        # Group blocks by hash
        for block in self._code_blocks:
            hash_groups[block.content_hash].append(block)
        
        # Find groups with multiple blocks (duplicates)
        duplicate_groups = []
        for content_hash, blocks in hash_groups.items():
            if len(blocks) > 1:
                # Filter out blocks from the same file at the same location
                unique_blocks = self._filter_unique_locations(blocks)
                if len(unique_blocks) > 1:
                    group = DuplicateGroup(unique_blocks, similarity_score=1.0)
                    duplicate_groups.append(group)
        
        return duplicate_groups
    
    def _filter_unique_locations(self, blocks: List[CodeBlock]) -> List[CodeBlock]:
        """Filter out blocks that are at the same location in the same file."""
        unique_blocks = []
        seen_locations = set()
        
        for block in blocks:
            location = (block.file_path, block.start_line, block.end_line)
            if location not in seen_locations:
                unique_blocks.append(block)
                seen_locations.add(location)
        
        return unique_blocks
    
    async def _find_similar_duplicates(self) -> List[DuplicateGroup]:
        """Find similar (but not exact) code blocks."""
        similar_groups = []
        processed_blocks = set()
        
        for i, block1 in enumerate(self._code_blocks):
            if block1 in processed_blocks:
                continue
            
            similar_blocks = [block1]
            
            for j, block2 in enumerate(self._code_blocks[i+1:], i+1):
                if block2 in processed_blocks:
                    continue
                
                # Skip if same file and overlapping lines
                if (block1.file_path == block2.file_path and 
                    self._blocks_overlap(block1, block2)):
                    continue
                
                similarity = self._calculate_similarity(block1.content, block2.content)
                
                if similarity >= self.similarity_threshold:
                    similar_blocks.append(block2)
                    processed_blocks.add(block2)
            
            if len(similar_blocks) > 1:
                # Calculate average similarity
                avg_similarity = self._calculate_group_similarity(similar_blocks)
                group = DuplicateGroup(similar_blocks, similarity_score=avg_similarity)
                similar_groups.append(group)
                
                for block in similar_blocks:
                    processed_blocks.add(block)
        
        return similar_groups
    
    def _blocks_overlap(self, block1: CodeBlock, block2: CodeBlock) -> bool:
        """Check if two blocks overlap in the same file."""
        if block1.file_path != block2.file_path:
            return False
        
        return not (block1.end_line < block2.start_line or block2.end_line < block1.start_line)
    
    def _calculate_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two code blocks."""
        lines1 = content1.splitlines()
        lines2 = content2.splitlines()
        
        # Use difflib to calculate similarity
        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        return matcher.ratio()
    
    def _calculate_group_similarity(self, blocks: List[CodeBlock]) -> float:
        """Calculate average similarity within a group of blocks."""
        if len(blocks) < 2:
            return 1.0
        
        total_similarity = 0.0
        comparisons = 0
        
        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                similarity = self._calculate_similarity(blocks[i].content, blocks[j].content)
                total_similarity += similarity
                comparisons += 1
        
        return total_similarity / comparisons if comparisons > 0 else 1.0
    
    async def _create_duplicate_issues(self, duplicate_groups: List[DuplicateGroup]) -> List[Duplicate]:
        """Create duplicate issues from duplicate groups."""
        issues = []
        
        for group in duplicate_groups:
            representative = group.representative_block
            if not representative:
                continue
            
            # Determine severity based on number of duplicates and lines
            severity = self._determine_severity(group)
            
            # Create refactoring suggestion
            refactoring_suggestion = self._generate_refactoring_suggestion(group)
            
            # Calculate confidence for refactoring
            refactoring_confidence = self._calculate_refactoring_confidence(group)
            
            # Create the duplicate issue
            issue = Duplicate(
                file_path=representative.file_path,
                line_number=representative.start_line,
                severity=severity,
                issue_type=IssueType.DUPLICATE_CODE,
                message=f"Duplicate code found in {group.duplicate_count} locations",
                description=f"Code block of {representative.lines_of_code} lines is duplicated "
                           f"across {group.duplicate_count} files with {group.similarity_score:.2%} similarity",
                duplicate_files=group.duplicate_files,
                similarity_score=group.similarity_score,
                lines_of_code=representative.lines_of_code,
                refactoring_suggestion=refactoring_suggestion,
                confidence=refactoring_confidence
            )
            
            issues.append(issue)
        
        return issues
    
    def _determine_severity(self, group: DuplicateGroup) -> IssueSeverity:
        """Determine severity based on duplicate characteristics."""
        lines = group.representative_block.lines_of_code
        count = group.duplicate_count
        similarity = group.similarity_score
        
        # Calculate severity score based on multiple factors
        severity_score = 0
        
        # Lines of code factor
        if lines >= 50:
            severity_score += 3
        elif lines >= 20:
            severity_score += 2
        elif lines >= 10:
            severity_score += 1
        
        # Duplicate count factor
        if count >= 5:
            severity_score += 3
        elif count >= 3:
            severity_score += 2
        elif count >= 2:
            severity_score += 1
        
        # Similarity factor (exact duplicates are worse)
        if similarity >= 0.95:
            severity_score += 2
        elif similarity >= 0.8:
            severity_score += 1
        
        # Map score to severity
        if severity_score >= 6:
            return IssueSeverity.CRITICAL
        elif severity_score >= 4:
            return IssueSeverity.HIGH
        elif severity_score >= 2:
            return IssueSeverity.MEDIUM
        else:
            return IssueSeverity.LOW
    
    def _calculate_refactoring_confidence(self, group: DuplicateGroup) -> float:
        """Calculate confidence score for refactoring suggestions."""
        confidence = group.similarity_score
        
        # Adjust confidence based on various factors
        representative = group.representative_block
        
        # Exact duplicates have higher confidence
        if group.similarity_score == 1.0:
            confidence = min(1.0, confidence + 0.1)
        
        # More duplicates increase confidence
        if group.duplicate_count >= 3:
            confidence = min(1.0, confidence + 0.05)
        
        # Larger blocks increase confidence
        if representative.lines_of_code >= 20:
            confidence = min(1.0, confidence + 0.05)
        
        # Function/class duplicates have higher confidence than line blocks
        if representative.block_type in ["function", "class"]:
            confidence = min(1.0, confidence + 0.1)
        
        # Analyze content for refactoring patterns
        content_analysis = self._analyze_duplicate_content(group)
        if any(content_analysis.values()):
            confidence = min(1.0, confidence + 0.05)
        
        return confidence
    
    def _generate_refactoring_suggestion(self, group: DuplicateGroup) -> str:
        """Generate refactoring suggestion for duplicate group."""
        representative = group.representative_block
        
        # Analyze the content for more specific suggestions
        content_analysis = self._analyze_duplicate_content(group)
        
        if representative.block_type == "function":
            if group.similarity_score == 1.0:
                return (f"Exact duplicate function detected. Consider extracting into a shared "
                       f"utility module. Found in {group.duplicate_count} locations: "
                       f"{', '.join(str(f) for f in group.duplicate_files[:3])}{'...' if len(group.duplicate_files) > 3 else ''}")
            else:
                return (f"Similar functions detected ({group.similarity_score:.1%} similarity). "
                       f"Consider creating a parameterized function or using a template pattern. "
                       f"Found in {group.duplicate_count} locations.")
        
        elif representative.block_type == "class":
            if group.similarity_score == 1.0:
                return (f"Exact duplicate class detected. Consider moving to a shared module "
                       f"or creating a base class. Found in {group.duplicate_count} locations.")
            else:
                return (f"Similar classes detected ({group.similarity_score:.1%} similarity). "
                       f"Consider creating a base class, mixin, or using composition pattern. "
                       f"Found in {group.duplicate_count} locations.")
        
        else:
            # Analyze content for specific patterns
            if content_analysis.get("has_loops"):
                return (f"Duplicate loop pattern detected ({representative.lines_of_code} lines). "
                       f"Consider extracting into a reusable iterator or generator function. "
                       f"Found in {group.duplicate_count} locations.")
            
            elif content_analysis.get("has_conditionals"):
                return (f"Duplicate conditional logic detected ({representative.lines_of_code} lines). "
                       f"Consider using a strategy pattern or configuration-driven approach. "
                       f"Found in {group.duplicate_count} locations.")
            
            elif content_analysis.get("has_calculations"):
                return (f"Duplicate calculation logic detected ({representative.lines_of_code} lines). "
                       f"Consider extracting into a utility function or using a formula engine. "
                       f"Found in {group.duplicate_count} locations.")
            
            else:
                return (f"Duplicate code block detected ({representative.lines_of_code} lines, "
                       f"{group.similarity_score:.1%} similarity). Consider extracting into a "
                       f"reusable function or method. Found in {group.duplicate_count} locations.")
    
    def _analyze_duplicate_content(self, group: DuplicateGroup) -> Dict[str, bool]:
        """Analyze duplicate content to provide better refactoring suggestions."""
        representative = group.representative_block
        content = representative.content.lower()
        
        analysis = {
            "has_loops": any(keyword in content for keyword in ["for ", "while ", "loop"]),
            "has_conditionals": any(keyword in content for keyword in ["if ", "elif ", "else:", "match ", "case "]),
            "has_calculations": any(keyword in content for keyword in ["+", "-", "*", "/", "**", "math.", "sum(", "max(", "min("]),
            "has_database": any(keyword in content for keyword in ["select", "insert", "update", "delete", "query", "cursor"]),
            "has_file_ops": any(keyword in content for keyword in ["open(", "read(", "write(", "file", "path"]),
            "has_network": any(keyword in content for keyword in ["request", "response", "http", "url", "api"]),
            "has_validation": any(keyword in content for keyword in ["validate", "check", "verify", "assert", "raise"]),
        }
        
        return analysis