#!/usr/bin/env python3
"""
IRDivergenceAnalyzer - Core analysis engine
Handles the main workflow of comparing Legacy vs NPM IR dumps.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any
import json
import os
import shutil
from pathlib import Path
import logging
from datetime import datetime

from data_types import PassDump, ComparisonConfig
from parser import IRDumpParser
from normalizer import IRNormalizer  
from reporter import ReportGenerator


class IRDivergenceAnalyzer:
    """
    Main analyzer class that orchestrates the IR divergence analysis.
    
    Workflow:
    1. Parse both legacy and NPM dump files
    2. Extract individual pass IR dumps to files
    3. Load and validate pass mappings
    4. Create chronological mapping between legacy and NPM passes
    5. Compare normalized IR content until first divergence
    6. Generate comprehensive report
    """
    
    def __init__(self, legacy_file: str, npm_file: str, mapping_file: str, 
                 output_dir: str, config: ComparisonConfig):
        self.legacy_file = Path(legacy_file)
        self.npm_file = Path(npm_file)
        self.mapping_file = Path(mapping_file)
        self.output_dir = Path(output_dir)
        self.config = config
        
        # Components
        self.parser = IRDumpParser(config)
        self.normalizer = IRNormalizer(config)
        self.reporter = ReportGenerator(config)
        
        # Analysis state
        self.legacy_dumps: List[PassDump] = []
        self.npm_dumps: List[PassDump] = []
        self.pass_mapping: Dict[str, str] = {}  # legacy_name -> npm_name
        
        # Setup logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Configure dual logging (file + terminal)"""
        
        # Create logs directory
        log_dir = self.output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove existing log file (fresh start each run)
        log_file = log_dir / "analyzer.log"
        if log_file.exists():
            log_file.unlink()
            
        # Setup logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler() if self.config.verbose else logging.NullHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("=== LLVM IR Divergence Analysis Started ===")
        self.logger.info(f"Legacy file: {self.legacy_file}")
        self.logger.info(f"NPM file: {self.npm_file}")
        self.logger.info(f"Mapping file: {self.mapping_file}")
        self.logger.info(f"Output directory: {self.output_dir}")
        
    def analyze_divergence(self) -> Dict[str, Any]:
        """
        Main analysis pipeline.
        Returns comprehensive results dictionary.
        """
        try:
            # Step 1: Parse and extract IR dumps
            if not self.config.quiet:
                print("Parsing IR dump files...")
            self._extract_ir_dumps()
            
            # Step 2: Load pass mappings  
            if not self.config.quiet:
                print("Loading pass mappings...")
            self._load_pass_mappings()
            
            # Step 3: Create chronological mapping
            if not self.config.quiet:
                print("Creating chronological pass mapping...")
            mapped_pairs, skipped_legacy = self._create_chronological_mapping()
            
            # Step 4: Find first divergence
            if not self.config.quiet:
                print("Comparing IR content...")
            divergence_result = self._find_first_divergence(mapped_pairs)
            
            # Step 5: Generate comprehensive report
            if not self.config.quiet:
                print("Generating analysis report...")
            report = self._generate_report(divergence_result, mapped_pairs, skipped_legacy)
            
            self.logger.info("=== Analysis completed successfully ===")
            return report
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            if self.config.verbose:
                self.logger.exception("Full traceback:")
            raise
            
    def _extract_ir_dumps(self):
        """Extract individual pass IR dumps to separate files"""
        
        # Create extraction directories
        legacy_dir = self.output_dir / "extracted" / "legacy"
        npm_dir = self.output_dir / "extracted" / "npm"
        legacy_dir.mkdir(parents=True, exist_ok=True)
        npm_dir.mkdir(parents=True, exist_ok=True)
        
        # Parse legacy dumps
        self.logger.info("Parsing legacy dump file...")
        self.legacy_dumps = self.parser.extract_legacy_dumps(
            self.legacy_file, legacy_dir
        )
        self.logger.info(f"Extracted {len(self.legacy_dumps)} legacy passes")
        
        # Parse NPM dumps  
        self.logger.info("Parsing NPM dump file...")
        self.npm_dumps = self.parser.extract_npm_dumps(
            self.npm_file, npm_dir
        )
        self.logger.info(f"Extracted {len(self.npm_dumps)} NPM passes")
        
        if not self.config.quiet:
            print(f"   Legacy passes: {len(self.legacy_dumps)}")
            print(f"   NPM passes: {len(self.npm_dumps)}")
            
    def _load_pass_mappings(self):
        """Load and validate pass mappings from JSON file"""
        
        try:
            with open(self.mapping_file, 'r') as f:
                self.pass_mapping = json.load(f)
                
            self.logger.info(f"Loaded {len(self.pass_mapping)} pass mappings")
            
            # Validate mapping structure
            self._validate_pass_mappings()
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Pass mapping file not found: {self.mapping_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in mapping file: {e}")
            
    def _validate_pass_mappings(self):
        """Validate pass mapping structure and detect issues"""
        
        # Check for duplicate values (two legacy -> same npm)
        npm_passes = list(self.pass_mapping.values())
        duplicates = [npm for npm in set(npm_passes) if npm_passes.count(npm) > 1]
        
        if duplicates:
            self.logger.warning(f"Found duplicate NPM pass mappings: {duplicates}")
            
        # TODO: Add more validation as needed
        
    def _create_chronological_mapping(self) -> Tuple[List[Tuple[PassDump, PassDump]], List[str]]:
        """
        Create one-to-one chronological mapping between legacy and NPM passes.
        Returns: (mapped_pairs, skipped_legacy_passes)
        """
        
        mapped_pairs = []
        used_npm_indices = set()
        last_npm_index = -1
        skipped_legacy = []
        explicitly_excluded = []
        
        for legacy_pass in self.legacy_dumps:
            # Check if pass is explicitly excluded
            if legacy_pass.pass_name in self.config.excluded_legacy_passes:
                explicitly_excluded.append(legacy_pass.pass_name)
                self.logger.info(f"Explicitly excluding legacy pass: {legacy_pass.pass_name}")
                continue
                
            # Get corresponding NPM pass name from mapping
            npm_pass_name = self.pass_mapping.get(legacy_pass.pass_name)
            
            if not npm_pass_name:
                skipped_legacy.append(legacy_pass.pass_name)
                self.logger.warning(f"No mapping found for legacy pass: {legacy_pass.pass_name}")
                continue
                
            # Check if mapped NPM pass is explicitly excluded
            if npm_pass_name in self.config.excluded_npm_passes:
                explicitly_excluded.append(f"{legacy_pass.pass_name} -> {npm_pass_name}")
                self.logger.info(f"Explicitly excluding mapped NPM pass: {npm_pass_name}")
                continue
                
            # Find earliest valid NPM match (respecting chronological order)
            npm_match = self._find_valid_npm_match(
                npm_pass_name, used_npm_indices, last_npm_index
            )
            
            if npm_match:
                npm_idx, npm_pass = npm_match
                mapped_pairs.append((legacy_pass, npm_pass))
                used_npm_indices.add(npm_idx)
                last_npm_index = npm_idx
                
                self.logger.debug(f"Mapped: {legacy_pass.pass_name} -> {npm_pass.pass_name}")
            else:
                skipped_legacy.append(legacy_pass.pass_name)
                self.logger.warning(f"No valid chronological match for: {legacy_pass.pass_name}")
                
        self.logger.info(f"Created {len(mapped_pairs)} pass mappings, skipped {len(skipped_legacy)}, explicitly excluded {len(explicitly_excluded)}")
        return mapped_pairs, skipped_legacy
        
    def _find_valid_npm_match(self, npm_pass_name: str, used_indices: set, 
                             last_index: int) -> Optional[Tuple[int, PassDump]]:
        """Find the earliest valid NPM pass match respecting chronological constraints"""
        
        for i, npm_pass in enumerate(self.npm_dumps):
            if (npm_pass.pass_name == npm_pass_name and 
                i not in used_indices and 
                i > last_index):
                return i, npm_pass
                
        return None
        
    def _find_first_divergence(self, mapped_pairs: List[Tuple[PassDump, PassDump]]) -> Dict[str, Any]:
        """
        Compare IR content for each mapped pair until first divergence.
        Returns divergence analysis results.
        """
        
        for i, (legacy_pass, npm_pass) in enumerate(mapped_pairs):
            self.logger.debug(f"Comparing pass pair {i}: {legacy_pass.pass_name} vs {npm_pass.pass_name}")
            
            # Load and normalize IR content
            legacy_ir = self._load_and_normalize_ir(legacy_pass.file_path)
            npm_ir = self._load_and_normalize_ir(npm_pass.file_path)
            
            # Compare normalized content
            if legacy_ir != npm_ir:
                self.logger.info(f"DIVERGENCE FOUND at pass pair {i}")
                self.logger.info(f"  Legacy: {legacy_pass.pass_name}")
                self.logger.info(f"  NPM: {npm_pass.pass_name}")
                
                return {
                    'divergence_found': True,
                    'divergence_index': i,
                    'legacy_pass': legacy_pass,
                    'npm_pass': npm_pass,
                    'last_common_index': i - 1 if i > 0 else None,
                    'last_common_legacy': mapped_pairs[i-1][0] if i > 0 else None,
                    'last_common_npm': mapped_pairs[i-1][1] if i > 0 else None,
                    'legacy_ir': legacy_ir,
                    'npm_ir': npm_ir
                }
                
        # No divergence found - all passes matched
        self.logger.info("NO DIVERGENCE FOUND - All compared passes have identical IR")
        return {'divergence_found': False}
        
    def _load_and_normalize_ir(self, file_path: str) -> str:
        """Load IR from file and apply normalization"""
        
        with open(file_path, 'r') as f:
            content = f.read()
            
        return self.normalizer.normalize(content)
        
    def _generate_report(self, divergence_result: Dict, mapped_pairs: List, 
                        skipped_legacy: List[str]) -> Dict[str, Any]:
        """Generate comprehensive analysis report"""
        
        return self.reporter.generate_report(
            divergence_result=divergence_result,
            mapped_pairs=mapped_pairs,
            skipped_legacy=skipped_legacy,
            legacy_passes=self.legacy_dumps,
            npm_passes=self.npm_dumps,
            legacy_total=len(self.legacy_dumps),
            npm_total=len(self.npm_dumps),
            output_dir=self.output_dir
        )
        
    def print_summary(self, result: Dict[str, Any]):
        """Print analysis summary to terminal"""
        self.reporter.print_terminal_summary(result)
