#!/usr/bin/env python3
"""
IRDumpParser - Parses LLVM IR dump files and extracts individual pass dumps
Handles both Legacy and NPM dump formats with boundary detection.
"""

import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional, TextIO
from dataclasses import dataclass

# Import from current directory
import sys
sys.path.insert(0, str(Path(__file__).parent))
from data_types import PassDump, ComparisonConfig, ParsedHeader


class IRDumpParser:
    """
    Parses LLVM IR dump files and extracts individual pass IR content.
    
    Handles two formats:
    - Legacy: *** IR Dump After PassName (pass-id) ***
    - NPM:    ; *** IR Dump After PassName on [target] ***
    """
    
    def __init__(self, config: ComparisonConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Compiled regex patterns for performance
        self.legacy_pattern = re.compile(
            r'^\s*#?\s*\*\*\* IR Dump After (.+) \*\*\*:?'
        )
        
        self.npm_pattern = re.compile(
            r'; \*\*\* IR Dump After (.+?) on (.+?) \*\*\*'
        )
        
    def extract_legacy_dumps(self, input_file: Path, output_dir: Path) -> List[PassDump]:
        """
        Extract all legacy pass dumps to individual files.
        Returns list of PassDump objects.
        """
        self.logger.info(f"Parsing legacy dump file: {input_file}")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            headers = self._find_legacy_headers(f)
            
        self.logger.info(f"Found {len(headers)} legacy pass headers")
        
        # Extract IR content for each pass
        passes = []
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, header in enumerate(headers):
            # Determine content boundaries
            start_line = header.line_number
            end_line = headers[i + 1].line_number if i + 1 < len(headers) else len(lines)
            
            # Extract IR content (skip header line)
            ir_content = self._extract_ir_content(lines, start_line + 1, end_line)
            
            # Generate output filename
            filename = self._generate_filename(i, header.pass_name, header.target)
            file_path = output_dir / filename
            
            # Save to file
            self._save_ir_to_file(ir_content, file_path)
            
            # Create PassDump object
            pass_dump = PassDump(
                pass_name=header.pass_name,
                pass_index=i,
                file_path=str(file_path)
            )
            passes.append(pass_dump)
            
            self.logger.debug(f"Extracted legacy pass {i}: {header.pass_name}")
            
        self.logger.info(f"Successfully extracted {len(passes)} legacy passes")
        return passes
        
    def extract_npm_dumps(self, input_file: Path, output_dir: Path) -> List[PassDump]:
        """
        Extract all NPM pass dumps to individual files.
        Returns list of PassDump objects.
        """
        self.logger.info(f"Parsing NPM dump file: {input_file}")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            headers = self._find_npm_headers(f)
            
        self.logger.info(f"Found {len(headers)} NPM pass headers")
        
        # Extract IR content for each pass
        passes = []
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, header in enumerate(headers):
            # Determine content boundaries
            start_line = header.line_number
            end_line = headers[i + 1].line_number if i + 1 < len(headers) else len(lines)
            
            # Extract IR content (skip header line)
            ir_content = self._extract_ir_content(lines, start_line + 1, end_line)
            
            # Generate output filename
            filename = self._generate_filename(i, header.pass_name, header.target)
            file_path = output_dir / filename
            
            # Save to file
            self._save_ir_to_file(ir_content, file_path)
            
            # Create PassDump object
            pass_dump = PassDump(
                pass_name=header.pass_name,
                pass_index=i,
                file_path=str(file_path)
            )
            passes.append(pass_dump)
            
            self.logger.debug(f"Extracted NPM pass {i}: {header.pass_name}")
            
        self.logger.info(f"Successfully extracted {len(passes)} NPM passes")
        return passes
        
    def _find_legacy_headers(self, file_handle: TextIO) -> List[ParsedHeader]:
        """Find all legacy pass headers in file"""
        headers = []
        line_number = 0
        
        for line in file_handle:
            line_number += 1
            line = line.rstrip()
            
            match = self.legacy_pattern.match(line)
            if match:
                full_content = match.group(1).strip()
                
                # Extract the last parentheses content as the pass identifier
                pass_identifier = self._extract_last_parentheses(full_content)
                
                header = ParsedHeader(
                    pass_name=pass_identifier,  # Use identifier as canonical name
                    original_line=line,
                    line_number=line_number,
                    dump_type="unknown",  # Legacy doesn't specify
                    target="unknown"      # Legacy doesn't specify
                )
                headers.append(header)
                
                self.logger.debug(f"Found legacy header at line {line_number}: {pass_identifier}")
                
        return headers
        
    def _extract_last_parentheses(self, content: str) -> str:
        """
        Extract content from the last parentheses in the string.
        For example: "Instrument function entry/exit (post inlining) (post-inline-ee-instrument)"
        Should return: "post-inline-ee-instrument"
        """
        # Find all parentheses pairs
        import re
        parentheses_matches = re.findall(r'\(([^)]+)\)', content)
        
        if parentheses_matches:
            # Return the last (rightmost) parentheses content
            return parentheses_matches[-1].strip()
        else:
            # Fallback: if no parentheses found, return the original content
            return content.strip()
        
    def _find_npm_headers(self, file_handle: TextIO) -> List[ParsedHeader]:
        """Find all NPM pass headers in file"""
        headers = []
        line_number = 0
        
        for line in file_handle:
            line_number += 1
            line = line.rstrip()
            
            match = self.npm_pattern.match(line)
            if match:
                pass_name = match.group(1).strip()
                target = match.group(2).strip()
                
                # Determine dump type
                if target == '[module]':
                    dump_type = "module"
                    target_name = "module"
                else:
                    dump_type = "function"  
                    target_name = target
                    
                header = ParsedHeader(
                    pass_name=pass_name,
                    original_line=line,
                    line_number=line_number,
                    dump_type=dump_type,
                    target=target_name
                )
                headers.append(header)
                
                self.logger.debug(f"Found NPM header at line {line_number}: {pass_name}")
                
        return headers
        
    def _extract_ir_content(self, lines: List[str], start_line: int, end_line: int) -> str:
        """
        Extract IR content between start and end lines.
        Returns cleaned content without the headers.
        """
        if start_line >= len(lines):
            return ""
            
        # Get content lines (convert from 1-based to 0-based indexing)
        content_lines = lines[start_line - 1:end_line - 1]
        
        # Join and return
        content = ''.join(content_lines)
        
        # Basic cleanup - remove trailing whitespace from each line
        cleaned_lines = []
        for line in content_lines:
            cleaned_lines.append(line.rstrip() + '\n')
            
        return ''.join(cleaned_lines)
        
    def _generate_filename(self, index: int, pass_name: str, target: str) -> str:
        """
        Generate clean filename for pass dump.
        Format: 001_PassName.ll or 001_PassName_target.ll
        """
        # Clean pass name for filesystem
        clean_name = self._sanitize_filename(pass_name)
        
        # Include target if it's a function
        if target and target != "unknown" and target != "module":
            clean_target = self._sanitize_filename(target)
            return f"{index:03d}_{clean_name}_{clean_target}.ll"
        else:
            return f"{index:03d}_{clean_name}.ll"
            
    def _sanitize_filename(self, name: str) -> str:
        """Clean up pass name to be filesystem-safe"""
        # Replace problematic characters
        clean = re.sub(r'[<>:"/\\|?*]', '_', name)
        clean = re.sub(r'\s+', '_', clean)
        clean = re.sub(r'[,()[\]]', '_', clean)
        clean = re.sub(r'_+', '_', clean)  # Collapse multiple underscores
        clean = clean.strip('_')  # Remove leading/trailing underscores
        
        # Limit length to avoid filesystem issues
        if len(clean) > 100:
            clean = clean[:100]
            
        return clean
        
    def _save_ir_to_file(self, content: str, file_path: Path):
        """Save IR content to file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            self.logger.error(f"Failed to save IR to {file_path}: {e}")
            raise
            
    def get_parser_stats(self) -> dict:
        """Return parsing statistics for debugging"""
        return {
            'legacy_pattern': self.legacy_pattern.pattern,
            'npm_pattern': self.npm_pattern.pattern,
        }
