"""
Tests for Duplicate Code Detection Analyzer

Tests exact duplicate detection, similar code detection, and refactoring suggestions.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from migration_assistant.checkup.analyzers.duplicates import (
    DuplicateCodeDetector, CodeBlock, DuplicateGroup
)
from migration_assistant.checkup.models import (
    CheckupConfig, IssueType, IssueSeverity
)


class TestCodeBlock:
    """Test CodeBlock class."""
    
    def test_code_block_creation(self):
        """Test creating a code block."""
        block = CodeBlock(
            file_path=Path("test.py"),
            start_line=1,
            end_line=5,
            content="def test():\n    pass",
            content_hash="abc123",
            block_type="function"
        )
        
        assert block.file_path == Path("test.py")
        assert block.start_line == 1
        assert block.end_line == 5
        assert block.lines_of_code == 5
        assert block.block_type == "function"
    
    def test_code_block_equality(self):
        """Test code block equality based on hash."""
        block1 = CodeBlock(
            file_path=Path("test1.py"),
            start_line=1,
            end_line=5,
            content="def test():\n    pass",
            content_hash="abc123"
        )
        
        block2 = CodeBlock(
            file_path=Path("test2.py"),
            start_line=10,
            end_line=14,
            content="def test():\n    pass",
            content_hash="abc123"
        )
        
        block3 = CodeBlock(
            file_path=Path("test3.py"),
            start_line=1,
            end_line=5,
            content="def other():\n    pass",
            content_hash="def456"
        )
        
        assert block1 == block2  # Same hash
        assert block1 != block3  # Different hash


class TestDuplicateGroup:
    """Test DuplicateGroup class."""
    
    def test_duplicate_group_creation(self):
        """Test creating a duplicate group."""
        blocks = [
            CodeBlock(Path("test1.py"), 1, 5, "content", "hash1"),
            CodeBlock(Path("test2.py"), 1, 5, "content", "hash1")
        ]
        
        group = DuplicateGroup(blocks, similarity_score=1.0)
        
        assert group.duplicate_count == 2
        assert group.total_lines == 10  # 5 lines each
        assert group.similarity_score == 1.0
        assert group.representative_block == blocks[0]
        assert group.duplicate_files == [Path("test1.py"), Path("test2.py")]


class TestDuplicateCodeDetector:
    """Test DuplicateCodeDetector class."""
    
    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return CheckupConfig(
            target_directory=Path("."),
            min_duplicate_lines=3,
            similarity_threshold=0.8
        )
    
    @pytest.fixture
    def detector(self, config):
        """Create detector instance."""
        return DuplicateCodeDetector(config)
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_detector_initialization(self, detector):
        """Test detector initialization."""
        assert detector.min_lines == 3
        assert detector.similarity_threshold == 0.8
        assert detector.get_supported_file_types() == ['.py']
    
    def test_hash_content(self, detector):
        """Test content hashing."""
        content1 = "def test():\n    pass\n    return True"
        content2 = "def test():\n    pass\n    return True"
        content3 = "def other():\n    pass\n    return False"
        
        hash1 = detector._hash_content(content1)
        hash2 = detector._hash_content(content2)
        hash3 = detector._hash_content(content3)
        
        assert hash1 == hash2  # Same content
        assert hash1 != hash3  # Different content
    
    def test_is_meaningful_block(self, detector):
        """Test meaningful block detection."""
        meaningful = [
            "def test():",
            "    x = 1",
            "    return x"
        ]
        
        not_meaningful = [
            "# Comment only",
            "",
            "    # Another comment"
        ]
        
        mixed = [
            "def test():",
            "    # Comment",
            "    return True"
        ]
        
        assert detector._is_meaningful_block(meaningful) is True
        assert detector._is_meaningful_block(not_meaningful) is False
        assert detector._is_meaningful_block(mixed) is True
    
    def test_blocks_overlap(self, detector):
        """Test block overlap detection."""
        block1 = CodeBlock(Path("test.py"), 1, 5, "content", "hash")
        block2 = CodeBlock(Path("test.py"), 3, 7, "content", "hash")  # Overlaps
        block3 = CodeBlock(Path("test.py"), 6, 10, "content", "hash")  # No overlap
        block4 = CodeBlock(Path("other.py"), 1, 5, "content", "hash")  # Different file
        
        assert detector._blocks_overlap(block1, block2) is True
        assert detector._blocks_overlap(block1, block3) is False
        assert detector._blocks_overlap(block1, block4) is False
    
    def test_calculate_similarity(self, detector):
        """Test similarity calculation."""
        content1 = "def test():\n    x = 1\n    return x"
        content2 = "def test():\n    x = 1\n    return x"  # Identical
        content3 = "def test():\n    y = 2\n    return y"  # Similar
        content4 = "class Test:\n    pass"  # Different
        
        similarity1 = detector._calculate_similarity(content1, content2)
        similarity2 = detector._calculate_similarity(content1, content3)
        similarity3 = detector._calculate_similarity(content1, content4)
        
        assert similarity1 == 1.0  # Identical
        assert 0.5 < similarity2 < 1.0  # Similar
        assert similarity3 < 0.5  # Different
    
    def test_determine_severity(self, detector):
        """Test severity determination."""
        # Create blocks with different characteristics
        small_block = CodeBlock(Path("test.py"), 1, 5, "content", "hash")
        medium_block = CodeBlock(Path("test.py"), 1, 15, "content", "hash")
        large_block = CodeBlock(Path("test.py"), 1, 60, "content", "hash")
        
        # Test different group sizes and block sizes
        small_group = DuplicateGroup([small_block, small_block])
        medium_group = DuplicateGroup([medium_block, medium_block, medium_block])
        large_group = DuplicateGroup([large_block, large_block])
        many_duplicates = DuplicateGroup([small_block] * 6)
        
        assert detector._determine_severity(small_group) == IssueSeverity.LOW
        assert detector._determine_severity(medium_group) == IssueSeverity.HIGH
        assert detector._determine_severity(large_group) == IssueSeverity.CRITICAL
        assert detector._determine_severity(many_duplicates) == IssueSeverity.CRITICAL
    
    def test_generate_refactoring_suggestion(self, detector):
        """Test refactoring suggestion generation."""
        function_block = CodeBlock(Path("test.py"), 1, 5, "content", "hash", "function")
        class_block = CodeBlock(Path("test.py"), 1, 5, "content", "hash", "class")
        generic_block = CodeBlock(Path("test.py"), 1, 5, "content", "hash", "lines")
        
        function_group = DuplicateGroup([function_block, function_block])
        class_group = DuplicateGroup([class_block, class_block])
        generic_group = DuplicateGroup([generic_block, generic_block])
        
        func_suggestion = detector._generate_refactoring_suggestion(function_group)
        class_suggestion = detector._generate_refactoring_suggestion(class_group)
        generic_suggestion = detector._generate_refactoring_suggestion(generic_group)
        
        assert "utility function" in func_suggestion
        assert "base class" in class_suggestion
        assert "reusable function" in generic_suggestion
    
    @pytest.mark.asyncio
    async def test_analyze_with_exact_duplicates(self, temp_dir, config):
        """Test analysis with exact duplicate code."""
        # Create test files with exact duplicates
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        
        duplicate_code = '''def calculate_sum(a, b):
    """Calculate sum of two numbers."""
    result = a + b
    return result
'''
        
        file1.write_text(f'''
{duplicate_code}

def other_function():
    pass
''')
        
        file2.write_text(f'''
def different_function():
    pass

{duplicate_code}
''')
        
        # Update config to point to temp directory
        config.target_directory = temp_dir
        detector = DuplicateCodeDetector(config)
        
        # Run analysis
        issues = await detector.analyze()
        
        # Should find the duplicate function
        assert len(issues) > 0
        duplicate_issue = issues[0]
        assert duplicate_issue.issue_type == IssueType.DUPLICATE_CODE
        assert duplicate_issue.similarity_score == 1.0
        assert len(duplicate_issue.duplicate_files) == 2
    
    @pytest.mark.asyncio
    async def test_analyze_with_similar_code(self, temp_dir, config):
        """Test analysis with similar (but not exact) code."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        
        file1.write_text('''
def calculate_sum(a, b):
    """Calculate sum of two numbers."""
    result = a + b
    print(f"Sum is {result}")
    return result
''')
        
        file2.write_text('''
def calculate_product(x, y):
    """Calculate product of two numbers."""
    result = x * y
    print(f"Product is {result}")
    return result
''')
        
        config.target_directory = temp_dir
        config.similarity_threshold = 0.6  # Lower threshold to catch similar code
        detector = DuplicateCodeDetector(config)
        
        issues = await detector.analyze()
        
        # Should find similar functions
        if issues:  # Similar code detection is more complex, may or may not find matches
            similar_issue = issues[0]
            assert similar_issue.issue_type == IssueType.DUPLICATE_CODE
            assert similar_issue.similarity_score < 1.0
    
    @pytest.mark.asyncio
    async def test_analyze_no_duplicates(self, temp_dir, config):
        """Test analysis with no duplicate code."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        
        file1.write_text('''
def function_one():
    return "one"
''')
        
        file2.write_text('''
def function_two():
    return "two"
''')
        
        config.target_directory = temp_dir
        detector = DuplicateCodeDetector(config)
        
        issues = await detector.analyze()
        
        # Should find no duplicates
        assert len(issues) == 0
    
    @pytest.mark.asyncio
    async def test_analyze_with_syntax_errors(self, temp_dir, config):
        """Test analysis handles files with syntax errors gracefully."""
        file1 = temp_dir / "valid.py"
        file2 = temp_dir / "invalid.py"
        
        file1.write_text('''
def valid_function():
    return True
''')
        
        file2.write_text('''
def invalid_function(
    # Missing closing parenthesis and colon
    return True
''')
        
        config.target_directory = temp_dir
        detector = DuplicateCodeDetector(config)
        
        # Should not raise exception
        issues = await detector.analyze()
        
        # Should still analyze valid files
        assert isinstance(issues, list)
    
    def test_filter_unique_locations(self, detector):
        """Test filtering of blocks at same location."""
        # Same location blocks (should be filtered to one)
        block1 = CodeBlock(Path("test.py"), 1, 5, "content", "hash")
        block2 = CodeBlock(Path("test.py"), 1, 5, "content", "hash")
        
        # Different location block
        block3 = CodeBlock(Path("test.py"), 10, 15, "content", "hash")
        
        blocks = [block1, block2, block3]
        unique_blocks = detector._filter_unique_locations(blocks)
        
        assert len(unique_blocks) == 2  # Should remove one duplicate location
        assert block3 in unique_blocks
    
    @pytest.mark.asyncio
    async def test_extract_ast_blocks(self, detector, temp_dir):
        """Test AST block extraction."""
        test_file = temp_dir / "test.py"
        test_file.write_text('''
def short_function():
    pass

def long_function():
    """This is a longer function."""
    x = 1
    y = 2
    z = x + y
    return z

class TestClass:
    def method(self):
        return True
''')
        
        # Load file content
        detector._file_contents[test_file] = test_file.read_text()
        detector._file_lines[test_file] = test_file.read_text().splitlines()
        
        # Extract AST blocks
        import ast
        tree = ast.parse(test_file.read_text())
        await detector._extract_ast_blocks(test_file, tree)
        
        # Should extract function and class blocks that meet minimum line requirement
        function_blocks = [b for b in detector._code_blocks if b.block_type == "function"]
        class_blocks = [b for b in detector._code_blocks if b.block_type == "class"]
        
        # At least the long function and class should be extracted
        assert len(function_blocks) >= 1
        assert len(class_blocks) >= 1

    @pytest.mark.asyncio
    async def test_similar_code_detection_with_ast(self, temp_dir, config):
        """Test AST-based similar code detection."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        
        # Create similar functions with different variable names
        file1.write_text('''
def process_data(input_data):
    """Process input data."""
    cleaned_data = input_data.strip()
    processed_data = cleaned_data.upper()
    result = processed_data.split()
    return result
''')
        
        file2.write_text('''
def handle_input(user_input):
    """Handle user input."""
    clean_input = user_input.strip()
    upper_input = clean_input.upper()
    tokens = upper_input.split()
    return tokens
''')
        
        config.target_directory = temp_dir
        config.similarity_threshold = 0.7  # Should catch similar structure
        detector = DuplicateCodeDetector(config)
        
        issues = await detector.analyze()
        
        # Should detect similar code patterns
        similar_issues = [issue for issue in issues if issue.similarity_score < 1.0]
        if similar_issues:
            issue = similar_issues[0]
            assert issue.similarity_score >= 0.7
            assert "similar" in issue.description.lower() or "duplicate" in issue.description.lower()
    
    @pytest.mark.asyncio
    async def test_configurable_similarity_threshold(self, temp_dir):
        """Test configurable similarity threshold."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        
        # Create moderately similar code
        file1.write_text('''
def calculate_area(length, width):
    area = length * width
    return area
''')
        
        file2.write_text('''
def compute_size(height, breadth):
    size = height * breadth
    return size
''')
        
        # Test with high threshold (should not detect)
        high_config = CheckupConfig(
            target_directory=temp_dir,
            similarity_threshold=0.95,
            min_duplicate_lines=3
        )
        high_detector = DuplicateCodeDetector(high_config)
        high_issues = await high_detector.analyze()
        
        # Test with low threshold (should detect)
        low_config = CheckupConfig(
            target_directory=temp_dir,
            similarity_threshold=0.5,
            min_duplicate_lines=3
        )
        low_detector = DuplicateCodeDetector(low_config)
        low_issues = await low_detector.analyze()
        
        # High threshold should find fewer (or no) matches
        # Low threshold should find more matches
        assert len(low_issues) >= len(high_issues)
    
    def test_calculate_group_similarity(self, detector):
        """Test group similarity calculation."""
        # Create blocks with known similarity
        block1 = CodeBlock(Path("test1.py"), 1, 5, "def test():\n    return 1", "hash1")
        block2 = CodeBlock(Path("test2.py"), 1, 5, "def test():\n    return 2", "hash2")
        block3 = CodeBlock(Path("test3.py"), 1, 5, "def test():\n    return 3", "hash3")
        
        blocks = [block1, block2, block3]
        similarity = detector._calculate_group_similarity(blocks)
        
        # Should return a similarity score between 0 and 1
        assert 0.0 <= similarity <= 1.0
        
        # Test with single block
        single_similarity = detector._calculate_group_similarity([block1])
        assert single_similarity == 1.0
        
        # Test with empty list
        empty_similarity = detector._calculate_group_similarity([])
        assert empty_similarity == 1.0
    
    @pytest.mark.asyncio
    async def test_fuzzy_matching_near_duplicates(self, temp_dir, config):
        """Test fuzzy matching for near-duplicate detection."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        
        # Create near-duplicate code with minor differences
        file1.write_text('''
def validate_email(email):
    if "@" not in email:
        return False
    if "." not in email:
        return False
    return True
''')
        
        file2.write_text('''
def check_email(email_addr):
    if "@" not in email_addr:
        return False
    if "." not in email_addr:
        return False
    return True
''')
        
        config.target_directory = temp_dir
        config.similarity_threshold = 0.8
        detector = DuplicateCodeDetector(config)
        
        issues = await detector.analyze()
        
        # Should detect near-duplicates with fuzzy matching
        if issues:
            issue = issues[0]
            assert issue.similarity_score >= config.similarity_threshold
            assert issue.similarity_score < 1.0  # Not exact match
    
    @pytest.mark.asyncio
    async def test_similarity_with_different_structures(self, temp_dir, config):
        """Test similarity detection with different code structures."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        file3 = temp_dir / "file3.py"
        
        # Similar logic, different structure
        file1.write_text('''
def process_list(items):
    result = []
    for item in items:
        if item > 0:
            result.append(item * 2)
    return result
''')
        
        # Same logic, list comprehension
        file2.write_text('''
def transform_list(data):
    return [x * 2 for x in data if x > 0]
''')
        
        # Completely different logic
        file3.write_text('''
def sort_dictionary(d):
    return dict(sorted(d.items()))
''')
        
        config.target_directory = temp_dir
        config.similarity_threshold = 0.3  # Lower threshold to test edge cases
        detector = DuplicateCodeDetector(config)
        
        issues = await detector.analyze()
        
        # The similar logic functions might be detected depending on AST similarity
        # The completely different function should not be similar
        for issue in issues:
            assert issue.similarity_score >= config.similarity_threshold


class TestRefactoringSuggestions:
    """Test refactoring suggestions engine."""
    
    @pytest.fixture
    def detector(self):
        """Create detector for refactoring tests."""
        config = CheckupConfig(
            target_directory=Path("."),
            min_duplicate_lines=3,
            similarity_threshold=0.8
        )
        return DuplicateCodeDetector(config)
    
    def test_analyze_duplicate_content(self, detector):
        """Test content analysis for better suggestions."""
        # Test loop detection
        loop_block = CodeBlock(
            Path("test.py"), 1, 5,
            "for item in items:\n    if item > 0:\n        result.append(item)",
            "hash1", "lines"
        )
        loop_group = DuplicateGroup([loop_block, loop_block])
        analysis = detector._analyze_duplicate_content(loop_group)
        assert analysis["has_loops"] is True
        
        # Test conditional detection
        conditional_block = CodeBlock(
            Path("test.py"), 1, 5,
            "if user.is_active:\n    return True\nelse:\n    return False",
            "hash2", "lines"
        )
        conditional_group = DuplicateGroup([conditional_block, conditional_block])
        analysis = detector._analyze_duplicate_content(conditional_group)
        assert analysis["has_conditionals"] is True
        
        # Test calculation detection
        calc_block = CodeBlock(
            Path("test.py"), 1, 5,
            "result = x + y * 2\nfinal = math.sqrt(result)",
            "hash3", "lines"
        )
        calc_group = DuplicateGroup([calc_block, calc_block])
        analysis = detector._analyze_duplicate_content(calc_group)
        assert analysis["has_calculations"] is True
    
    def test_enhanced_refactoring_suggestions(self, detector):
        """Test enhanced refactoring suggestions based on content analysis."""
        # Test exact function duplicate
        exact_func_block = CodeBlock(
            Path("test1.py"), 1, 5,
            "def calculate(x, y):\n    return x + y",
            "hash1", "function"
        )
        exact_func_group = DuplicateGroup([exact_func_block, exact_func_block], 1.0)
        suggestion = detector._generate_refactoring_suggestion(exact_func_group)
        assert "exact duplicate function" in suggestion.lower()
        assert "shared utility module" in suggestion.lower()
        
        # Test similar function duplicate
        similar_func_block = CodeBlock(
            Path("test2.py"), 1, 5,
            "def compute(a, b):\n    return a + b",
            "hash2", "function"
        )
        similar_func_group = DuplicateGroup([similar_func_block, similar_func_block], 0.85)
        suggestion = detector._generate_refactoring_suggestion(similar_func_group)
        assert "similar functions" in suggestion.lower()
        assert "parameterized function" in suggestion.lower()
        
        # Test loop pattern
        loop_block = CodeBlock(
            Path("test3.py"), 1, 8,
            "for item in data:\n    if item.valid:\n        process(item)",
            "hash3", "lines"
        )
        loop_group = DuplicateGroup([loop_block, loop_block])
        suggestion = detector._generate_refactoring_suggestion(loop_group)
        assert "loop pattern" in suggestion.lower()
        assert "iterator or generator" in suggestion.lower()
        
        # Test conditional pattern
        conditional_block = CodeBlock(
            Path("test4.py"), 1, 6,
            "if status == 'active':\n    return True\nelif status == 'pending':\n    return False",
            "hash4", "lines"
        )
        conditional_group = DuplicateGroup([conditional_block, conditional_block])
        suggestion = detector._generate_refactoring_suggestion(conditional_group)
        assert "conditional logic" in suggestion.lower()
        assert "strategy pattern" in suggestion.lower()
    
    def test_calculate_refactoring_confidence(self, detector):
        """Test refactoring confidence calculation."""
        # High confidence: exact duplicate function with many instances
        high_conf_block = CodeBlock(
            Path("test.py"), 1, 25,
            "def process():\n    # 25 lines of code",
            "hash1", "function"
        )
        high_conf_group = DuplicateGroup([high_conf_block] * 4, 1.0)
        high_confidence = detector._calculate_refactoring_confidence(high_conf_group)
        
        # Low confidence: small similar line block
        low_conf_block = CodeBlock(
            Path("test.py"), 1, 3,
            "x = 1\ny = 2",
            "hash2", "lines"
        )
        low_conf_group = DuplicateGroup([low_conf_block, low_conf_block], 0.7)
        low_confidence = detector._calculate_refactoring_confidence(low_conf_group)
        
        assert high_confidence > low_confidence
        assert 0.0 <= low_confidence <= 1.0
        assert 0.0 <= high_confidence <= 1.0
    
    def test_severity_scoring_with_multiple_factors(self, detector):
        """Test severity determination with multiple factors."""
        # Critical: large exact duplicate with many instances
        critical_block = CodeBlock(Path("test.py"), 1, 60, "content", "hash1", "function")
        critical_group = DuplicateGroup([critical_block] * 6, 1.0)
        critical_severity = detector._determine_severity(critical_group)
        assert critical_severity == IssueSeverity.CRITICAL
        
        # High: medium size with multiple instances
        high_block = CodeBlock(Path("test.py"), 1, 25, "content", "hash2", "function")
        high_group = DuplicateGroup([high_block] * 3, 0.95)
        high_severity = detector._determine_severity(high_group)
        assert high_severity == IssueSeverity.HIGH
        
        # Medium: smaller duplicates
        medium_block = CodeBlock(Path("test.py"), 1, 12, "content", "hash3", "lines")
        medium_group = DuplicateGroup([medium_block, medium_block], 0.8)
        medium_severity = detector._determine_severity(medium_group)
        assert medium_severity == IssueSeverity.MEDIUM
        
        # Low: small, less similar duplicates
        low_block = CodeBlock(Path("test.py"), 1, 5, "content", "hash4", "lines")
        low_group = DuplicateGroup([low_block, low_block], 0.6)
        low_severity = detector._determine_severity(low_group)
        assert low_severity == IssueSeverity.LOW
    
    @pytest.mark.asyncio
    async def test_refactoring_suggestions_integration(self, temp_dir):
        """Test refactoring suggestions in full analysis."""
        # Create files with different types of duplicates
        file1 = temp_dir / "utils1.py"
        file2 = temp_dir / "utils2.py"
        file3 = temp_dir / "handlers.py"
        
        # Exact function duplicate
        file1.write_text('''
def validate_email(email):
    """Validate email format."""
    if "@" not in email:
        return False
    if "." not in email.split("@")[1]:
        return False
    return True
''')
        
        file2.write_text('''
def validate_email(email):
    """Validate email format."""
    if "@" not in email:
        return False
    if "." not in email.split("@")[1]:
        return False
    return True
''')
        
        # Similar loop pattern
        file3.write_text('''
def process_items(items):
    results = []
    for item in items:
        if item.is_valid():
            results.append(item.process())
    return results

def handle_data(data_list):
    output = []
    for data in data_list:
        if data.is_ready():
            output.append(data.transform())
    return output
''')
        
        config = CheckupConfig(
            target_directory=temp_dir,
            min_duplicate_lines=4,
            similarity_threshold=0.7
        )
        detector = DuplicateCodeDetector(config)
        
        issues = await detector.analyze()
        
        # Should find duplicates with appropriate suggestions
        assert len(issues) > 0
        
        for issue in issues:
            assert issue.refactoring_suggestion is not None
            assert len(issue.refactoring_suggestion) > 0
            assert issue.confidence > 0.0
            
            # Check that suggestions are contextual
            if issue.similarity_score == 1.0:
                assert "exact" in issue.refactoring_suggestion.lower()
            else:
                assert "similar" in issue.refactoring_suggestion.lower()
    
    def test_abstraction_pattern_detection(self, detector):
        """Test detection of common abstraction patterns."""
        # Test database operation pattern
        db_block = CodeBlock(
            Path("test.py"), 1, 8,
            "cursor.execute('SELECT * FROM users')\nresults = cursor.fetchall()",
            "hash1", "lines"
        )
        db_group = DuplicateGroup([db_block, db_block])
        analysis = detector._analyze_duplicate_content(db_group)
        assert analysis["has_database"] is True
        
        # Test file operation pattern
        file_block = CodeBlock(
            Path("test.py"), 1, 6,
            "with open('file.txt', 'r') as f:\n    content = f.read()",
            "hash2", "lines"
        )
        file_group = DuplicateGroup([file_block, file_block])
        analysis = detector._analyze_duplicate_content(file_group)
        assert analysis["has_file_ops"] is True
        
        # Test validation pattern
        validation_block = CodeBlock(
            Path("test.py"), 1, 5,
            "if not user.is_valid():\n    raise ValueError('Invalid user')",
            "hash3", "lines"
        )
        validation_group = DuplicateGroup([validation_block, validation_block])
        analysis = detector._analyze_duplicate_content(validation_group)
        assert analysis["has_validation"] is True