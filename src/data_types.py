#!/usr/bin/env python3
"""
Data structures and configuration for LLVM IR Divergence Analyzer
Shared types used across all modules.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any


@dataclass
class PassDump:
    """Represents a single pass IR dump"""
    pass_name: str           # Original pass name from dump
    pass_index: int          # Order in pipeline (0, 1, 2, ...)
    file_path: str           # Path to extracted IR file


@dataclass  
class ComparisonConfig:
    """Configuration for IR comparison and normalization"""
    # Basic normalization (always enabled)
    ignore_whitespace: bool = True
    ignore_empty_lines: bool = True
    
    # Optional normalization
    ignore_temp_vars: bool = True
    ignore_labels: bool = True
    ignore_metadata: bool = True      # Lines starting with !
    ignore_debug_info: bool = True    
    ignore_comments: bool = False     # ; comments
    
    # Behavior
    verbose: bool = False
    quiet: bool = False
    
    # Excluded passes (explicitly skip)
    excluded_legacy_passes: List[str] = None
    excluded_npm_passes: List[str] = None
    
    def __post_init__(self):
        """Initialize empty lists if None"""
        if self.excluded_legacy_passes is None:
            self.excluded_legacy_passes = []
        if self.excluded_npm_passes is None:
            self.excluded_npm_passes = []


@dataclass
class ParsedHeader:
    """Represents a parsed pass header"""
    pass_name: str           # Clean pass name
    original_line: str       # Original header line
    line_number: int         # Line number in file
    dump_type: str           # "module", "function", or "unknown"
    target: str              # function name or "module" or "unknown"
