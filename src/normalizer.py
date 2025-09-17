#!/usr/bin/env python3
"""
IRNormalizer - Normalizes LLVM IR content for semantic comparison
Handles configurable normalization rules for consistent comparison.
"""

import re
import logging
from typing import Dict, List, Set
from dataclasses import dataclass

# Import from current directory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from data_types import ComparisonConfig


class IRNormalizer:
    """
    Normalizes LLVM IR content for semantic comparison.
    
    Configurable normalization includes:
    - Temporary variable names (%1, %2, %temp.1) 
    - Basic block labels (bb1, entry.2)
    - Metadata lines (starting with !)
    - Whitespace and empty lines
    - Debug information
    - Comments (starting with ;)
    """
    
    def __init__(self, config: ComparisonConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Pre-compile regex patterns for performance
        self._compile_patterns()
        
    def _compile_patterns(self):
        """Compile regex patterns for normalization"""
        
        # Temporary variables: %1, %2, %temp.1, %call.i, etc.
        self.temp_var_pattern = re.compile(r'%[a-zA-Z_][a-zA-Z0-9_]*\.?[0-9]*')
        
        # Basic block labels: label1:, entry.2:, bb.3:, etc.  
        self.label_pattern = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*\.?[0-9]*):')
        
        # Metadata lines: !0 = metadata, !dbg !1, etc.
        self.metadata_pattern = re.compile(r'^!.*$')
        
        # Comments: ; comment text
        self.comment_pattern = re.compile(r';.*$')
        
        # Debug info in instructions: !dbg !123
        self.debug_info_pattern = re.compile(r', !dbg ![0-9]+')
        
    def normalize(self, ir_content: str) -> str:
        """
        Apply configured normalization to IR content.
        Returns normalized IR string.
        """
        lines = ir_content.split('\n')
        normalized_lines = []
        
        # Counters for consistent renaming
        temp_var_counter = 0
        label_counter = 0
        temp_var_map: Dict[str, str] = {}
        label_map: Dict[str, str] = {}
        
        for line in lines:
            normalized_line = line
            
            # Skip empty lines if configured
            if self.config.ignore_empty_lines and not line.strip():
                continue
                
            # Skip metadata lines if configured
            if self.config.ignore_metadata and self.metadata_pattern.match(line.strip()):
                continue
                
            # Remove comments if configured
            if self.config.ignore_comments:
                normalized_line = self.comment_pattern.sub('', normalized_line)
                
            # Remove debug info if configured
            if self.config.ignore_debug_info:
                normalized_line = self.debug_info_pattern.sub('', normalized_line)
                
            # Normalize basic block labels if configured
            if self.config.ignore_labels:
                normalized_line, label_counter, label_map = self._normalize_labels(
                    normalized_line, label_counter, label_map
                )
                
            # Normalize temporary variables if configured
            if self.config.ignore_temp_vars:
                normalized_line, temp_var_counter, temp_var_map = self._normalize_temp_vars(
                    normalized_line, temp_var_counter, temp_var_map
                )
                
            # Normalize whitespace if configured
            if self.config.ignore_whitespace:
                normalized_line = self._normalize_whitespace(normalized_line)
                
            # Add normalized line if it's not empty
            if normalized_line.strip():
                normalized_lines.append(normalized_line)
                
        result = '\n'.join(normalized_lines)
        
        self.logger.debug(f"Normalized IR: {len(lines)} -> {len(normalized_lines)} lines")
        return result
        
    def _normalize_temp_vars(self, line: str, counter: int, var_map: Dict[str, str]) -> tuple:
        """
        Normalize temporary variable names consistently.
        Returns (normalized_line, updated_counter, updated_map)
        """
        def replace_temp_var(match):
            nonlocal counter
            original = match.group(0)
            
            if original not in var_map:
                var_map[original] = f'%temp_{counter}'
                counter += 1
                
            return var_map[original]
            
        normalized = self.temp_var_pattern.sub(replace_temp_var, line)
        return normalized, counter, var_map
        
    def _normalize_labels(self, line: str, counter: int, label_map: Dict[str, str]) -> tuple:
        """
        Normalize basic block labels consistently.
        Returns (normalized_line, updated_counter, updated_map)
        """
        def replace_label(match):
            nonlocal counter
            original = match.group(1)
            
            if original not in label_map:
                label_map[original] = f'label_{counter}'
                counter += 1
                
            return f'{label_map[original]}:'
            
        normalized = self.label_pattern.sub(replace_label, line)
        
        # Also need to replace label references in br, phi, etc.
        # This is more complex and may need instruction-specific handling
        for original, normalized_label in label_map.items():
            # Replace references like "br label %original" 
            normalized = re.sub(
                rf'\b{re.escape(original)}\b', 
                normalized_label.rstrip(':'), 
                normalized
            )
            
        return normalized, counter, label_map
        
    def _normalize_whitespace(self, line: str) -> str:
        """Normalize whitespace in line"""
        # Replace multiple spaces with single space
        normalized = re.sub(r'\s+', ' ', line)
        # Strip leading/trailing whitespace
        return normalized.strip()
        
    def get_normalization_stats(self, original: str, normalized: str) -> dict:
        """Get statistics about normalization process"""
        original_lines = len(original.split('\n'))
        normalized_lines = len(normalized.split('\n'))
        
        return {
            'original_lines': original_lines,
            'normalized_lines': normalized_lines,
            'lines_removed': original_lines - normalized_lines,
            'reduction_percent': ((original_lines - normalized_lines) / original_lines * 100) if original_lines > 0 else 0
        }
