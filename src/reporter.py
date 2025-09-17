#!/usr/bin/env python3
"""
ReportGenerator - Generates comprehensive analysis reports
Creates JSON reports, terminal summaries, and diff files.
"""

import json
import logging
import difflib
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime

# Import from current directory
import sys
sys.path.insert(0, str(Path(__file__).parent))
from data_types import ComparisonConfig, PassDump


class ReportGenerator:
    """
    Generates comprehensive reports for IR divergence analysis.
    
    Outputs:
    - JSON detailed report
    - Terminal summary
    - Diff files for divergent passes
    - Analysis statistics
    """
    
    def __init__(self, config: ComparisonConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        
    def generate_report(self, divergence_result: Dict, mapped_pairs: List[Tuple], 
                       skipped_legacy: List[str], legacy_passes: List[PassDump], 
                       npm_passes: List[PassDump], legacy_total: int, npm_total: int,
                       output_dir: Path) -> Dict[str, Any]:
        """
        Generate comprehensive analysis report.
        Returns report dictionary and saves to files.
        """
        
        # Create analysis directory
        analysis_dir = output_dir / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        
        # Build comprehensive report
        report = self._build_report_data(
            divergence_result, mapped_pairs, skipped_legacy, 
            legacy_total, npm_total
        )
        
        # Save JSON report
        json_file = analysis_dir / "divergence_report.json"
        self._save_json_report(report, json_file)
        
        # Generate diff file if divergence found
        if divergence_result.get('divergence_found'):
            diff_file = analysis_dir / "first_divergence_diff.txt"
            self._generate_diff_file(divergence_result, diff_file)
            
        # Save mapping information
        mapping_file = analysis_dir / "pass_mapping_used.json"
        self._save_mapping_info(mapped_pairs, skipped_legacy, mapping_file)
        
        # Generate visualization file
        logs_dir = output_dir / "logs"
        logs_dir.mkdir(exist_ok=True)
        viz_file = logs_dir / "pass_mapping_visualization.txt"
        self._generate_visualization_file(mapped_pairs, skipped_legacy, divergence_result, 
                                        viz_file, legacy_passes, npm_passes, legacy_total, npm_total)
        
        # Add file paths to report
        report['output_files'] = {
            'json_report': str(json_file),
            'diff_file': str(diff_file) if divergence_result.get('divergence_found') else None,
            'mapping_file': str(mapping_file),
            'visualization_file': str(viz_file)
        }
        
        self.logger.info("Generated comprehensive analysis report")
        return report
        
    def _build_report_data(self, divergence_result: Dict, mapped_pairs: List[Tuple],
                          skipped_legacy: List[str], legacy_total: int, 
                          npm_total: int) -> Dict[str, Any]:
        """Build the main report data structure"""
        
        report = {
            'analysis_info': {
                'timestamp': datetime.now().isoformat(),
                'tool_version': '1.0',
                'analysis_type': 'llvm_ir_divergence'
            },
            'summary': {
                'total_legacy_passes': legacy_total,
                'total_npm_passes': npm_total,
                'successfully_mapped': len(mapped_pairs),
                'skipped_legacy_passes': len(skipped_legacy),
                'unused_npm_passes': npm_total - len(mapped_pairs)
            },
            'divergence_analysis': self._build_divergence_info(divergence_result, mapped_pairs),
            'mapping_details': self._build_mapping_details(mapped_pairs, skipped_legacy),
            'success': True
        }
        
        return report
        
    def _build_divergence_info(self, divergence_result: Dict, mapped_pairs: List[Tuple]) -> Dict[str, Any]:
        """Build divergence analysis information"""
        
        if not divergence_result.get('divergence_found'):
            return {
                'divergence_found': False,
                'message': 'No divergence found - all compared passes have identical IR',
                'total_compared_passes': len(mapped_pairs)
            }
            
        # Divergence found
        divergence_index = divergence_result['divergence_index']
        legacy_pass = divergence_result['legacy_pass']
        npm_pass = divergence_result['npm_pass']
        
        result = {
            'divergence_found': True,
            'first_divergent_pass': {
                'index': divergence_index,
                'legacy_pass': legacy_pass.pass_name,
                'npm_pass': npm_pass.pass_name,
                'legacy_file': legacy_pass.file_path,
                'npm_file': npm_pass.file_path,
                'legacy_position': legacy_pass.pass_index,
                'npm_position': npm_pass.pass_index
            },
            'passes_compared_before_divergence': divergence_index,
            'total_compared_passes': len(mapped_pairs)
        }
        
        # Add last common pass info if available
        if divergence_result.get('last_common_index') is not None:
            last_common_legacy = divergence_result['last_common_legacy']
            last_common_npm = divergence_result['last_common_npm']
            
            result['last_common_pass'] = {
                'index': divergence_result['last_common_index'],
                'legacy_pass': last_common_legacy.pass_name,
                'npm_pass': last_common_npm.pass_name,
                'legacy_file': last_common_legacy.file_path,
                'npm_file': last_common_npm.file_path,
                'legacy_position': last_common_legacy.pass_index,
                'npm_position': last_common_npm.pass_index
            }
        else:
            result['last_common_pass'] = None
            
        return result
        
    def _build_mapping_details(self, mapped_pairs: List[Tuple], skipped_legacy: List[str]) -> Dict[str, Any]:
        """Build detailed mapping information"""
        
        successful_mappings = []
        for i, (legacy_pass, npm_pass) in enumerate(mapped_pairs):
            successful_mappings.append({
                'pair_index': i,
                'legacy_pass': legacy_pass.pass_name,
                'npm_pass': npm_pass.pass_name,
                'legacy_file': legacy_pass.file_path,
                'npm_file': npm_pass.file_path
            })
            
        return {
            'successful_mappings': successful_mappings,
            'skipped_legacy_passes': skipped_legacy,
            'mapping_success_rate': len(mapped_pairs) / (len(mapped_pairs) + len(skipped_legacy)) if (len(mapped_pairs) + len(skipped_legacy)) > 0 else 0
        }
        
    def _save_json_report(self, report: Dict[str, Any], file_path: Path):
        """Save report to JSON file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved JSON report to: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save JSON report: {e}")
            raise
            
    def _generate_diff_file(self, divergence_result: Dict, file_path: Path):
        """Generate detailed diff file for divergent passes"""
        
        legacy_ir = divergence_result.get('legacy_ir', '')
        npm_ir = divergence_result.get('npm_ir', '')
        legacy_pass = divergence_result['legacy_pass']
        npm_pass = divergence_result['npm_pass']
        
        # Generate unified diff
        legacy_lines = legacy_ir.splitlines(keepends=True)
        npm_lines = npm_ir.splitlines(keepends=True)
        
        diff = difflib.unified_diff(
            legacy_lines,
            npm_lines,
            fromfile=f"legacy/{legacy_pass.pass_name}",
            tofile=f"npm/{npm_pass.pass_name}",
            lineterm=''
        )
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"LLVM IR Divergence Diff\n")
                f.write(f"======================\n\n")
                f.write(f"Legacy Pass: {legacy_pass.pass_name}\n")
                f.write(f"NPM Pass:    {npm_pass.pass_name}\n")
                f.write(f"Generated:   {datetime.now().isoformat()}\n\n")
                f.write("Unified Diff:\n")
                f.write("-------------\n")
                f.writelines(diff)
                
            self.logger.info(f"Saved diff file to: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save diff file: {e}")
            raise
            
    def _save_mapping_info(self, mapped_pairs: List[Tuple], skipped_legacy: List[str], file_path: Path):
        """Save detailed mapping information"""
        
        mapping_info = {
            'successful_mappings': {
                legacy_pass.pass_name: npm_pass.pass_name 
                for legacy_pass, npm_pass in mapped_pairs
            },
            'skipped_legacy_passes': skipped_legacy,
            'statistics': {
                'total_mappings': len(mapped_pairs),
                'skipped_passes': len(skipped_legacy),
                'success_rate': len(mapped_pairs) / (len(mapped_pairs) + len(skipped_legacy)) if (len(mapped_pairs) + len(skipped_legacy)) > 0 else 0
            }
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(mapping_info, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved mapping info to: {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save mapping info: {e}")
            raise
            
    def print_terminal_summary(self, result: Dict[str, Any]):
        """Print analysis summary to terminal"""
        
        if self.config.quiet:
            return
            
        print("\n" + "="*60)
        print("LLVM IR DIVERGENCE ANALYSIS RESULTS")
        print("="*60)
        
        # Summary statistics
        summary = result.get('summary', {})
        print(f"SUMMARY:")
        print(f"   Legacy passes:     {summary.get('total_legacy_passes', 0)}")
        print(f"   NPM passes:        {summary.get('total_npm_passes', 0)}")
        print(f"   Successfully mapped: {summary.get('successfully_mapped', 0)}")
        print(f"   Skipped passes:    {summary.get('skipped_legacy_passes', 0)}")
        
        # Divergence results
        divergence = result.get('divergence_analysis', {})
        if divergence.get('divergence_found'):
            print(f"\nFIRST DIVERGENCE FOUND:")
            first_div = divergence['first_divergent_pass']
            print(f"   Position:      Pass pair #{first_div['index']}")
            print(f"   Legacy Pass:   \"{first_div['legacy_pass']}\" (#{first_div['legacy_position']} in legacy pipeline)")
            print(f"   NPM Pass:      \"{first_div['npm_pass']}\" (#{first_div['npm_position']} in NPM pipeline)")
            
            if divergence.get('last_common_pass'):
                last_common = divergence['last_common_pass']
                print(f"\nLAST COMMON PASS:")
                print(f"   Position:      Pass pair #{last_common['index']}")
                print(f"   Legacy Pass:   \"{last_common['legacy_pass']}\" (#{last_common['legacy_position']} in legacy pipeline)")
                print(f"   NPM Pass:      \"{last_common['npm_pass']}\" (#{last_common['npm_position']} in NPM pipeline)")
        else:
            print(f"\nNO DIVERGENCE FOUND!")
            print(f"   All {divergence.get('total_compared_passes', 0)} compared passes have identical IR")
            
        # Output files
        output_files = result.get('output_files', {})
        print(f"\nOUTPUT FILES:")
        print(f"   JSON Report:   {output_files.get('json_report', 'N/A')}")
        if output_files.get('diff_file'):
            print(f"   Diff File:     {output_files.get('diff_file')}")
        print(f"   Mapping Info:  {output_files.get('mapping_file', 'N/A')}")
        print(f"   Visualization: {output_files.get('visualization_file', 'N/A')}")
        
        print("="*60 + "\n")

    def _generate_visualization_file(self, mapped_pairs: List[Tuple], skipped_legacy: List[str], 
                                   divergence_result: Dict, file_path: Path, 
                                   legacy_passes: List[PassDump], npm_passes: List[PassDump],
                                   legacy_total: int, npm_total: int):
        """Generate pass mapping visualization file with interleaved chronological display"""
        
        # Create mapping dictionaries
        legacy_to_npm = {}  # legacy_idx -> (npm_idx, is_divergent)
        npm_to_legacy = {}  # npm_idx -> (legacy_idx, is_divergent)
        mapped_legacy_indices = set()
        mapped_npm_indices = set()
        
        for legacy_pass, npm_pass in mapped_pairs:
            legacy_idx = legacy_pass.pass_index
            npm_idx = npm_pass.pass_index
            
            # Check if this is the divergent pair
            is_divergent = (divergence_result.get('divergence_found') and
                          legacy_pass.pass_name == divergence_result['legacy_pass'].pass_name and
                          npm_pass.pass_name == divergence_result['npm_pass'].pass_name)
            
            legacy_to_npm[legacy_idx] = (npm_idx, is_divergent)
            npm_to_legacy[npm_idx] = (legacy_idx, is_divergent)
            mapped_legacy_indices.add(legacy_idx)
            mapped_npm_indices.add(npm_idx)
        
        # Sort mappings by NPM index to create anchor points
        sorted_mappings = sorted(legacy_to_npm.items(), key=lambda x: x[1][0])  # Sort by NPM index
        
        # Generate the interleaved chronological display
        output_lines = []
        
        # Track what we've processed
        processed_legacy = set()
        processed_npm = set()
        
        prev_npm_idx = -1
        prev_legacy_idx = -1
        
        for legacy_idx, (npm_idx, is_divergent) in sorted_mappings:
            # First, fill in unmapped Legacy passes between previous mapping and current mapping
            for l_idx in range(prev_legacy_idx + 1, legacy_idx):
                if l_idx < len(legacy_passes):
                    legacy_pass = legacy_passes[l_idx]
                    legacy_info = f"(#{legacy_pass.pass_index:3d}) {legacy_pass.pass_name}"
                    output_lines.append((legacy_info, "", ""))
                    processed_legacy.add(l_idx)
            
            # Second, fill in unmapped NPM passes between previous mapping and current mapping
            for n_idx in range(prev_npm_idx + 1, npm_idx):
                if n_idx < len(npm_passes):
                    npm_pass = npm_passes[n_idx]
                    npm_info = f"(#{npm_pass.pass_index:3d}) {npm_pass.pass_name}"
                    output_lines.append(("", "", npm_info))
                    processed_npm.add(n_idx)
            
            # Add the mapping pair
            legacy_pass = legacy_passes[legacy_idx]
            npm_pass = npm_passes[npm_idx]
            legacy_info = f"(#{legacy_pass.pass_index:3d}) {legacy_pass.pass_name}"
            npm_info = f"(#{npm_pass.pass_index:3d}) {npm_pass.pass_name}"
            arrow = " <-D-> " if is_divergent else " <---> "
            
            output_lines.append((legacy_info, arrow, npm_info))
            processed_legacy.add(legacy_idx)
            processed_npm.add(npm_idx)
            
            prev_npm_idx = npm_idx
            prev_legacy_idx = legacy_idx
        
        # Add remaining unmapped Legacy passes after last mapping
        for l_idx in range(prev_legacy_idx + 1, len(legacy_passes)):
            legacy_pass = legacy_passes[l_idx]
            legacy_info = f"(#{legacy_pass.pass_index:3d}) {legacy_pass.pass_name}"
            output_lines.append((legacy_info, "", ""))
            processed_legacy.add(l_idx)
        
        # Add remaining unmapped NPM passes after last mapping
        for n_idx in range(prev_npm_idx + 1, len(npm_passes)):
            npm_pass = npm_passes[n_idx]
            npm_info = f"(#{npm_pass.pass_index:3d}) {npm_pass.pass_name}"
            output_lines.append(("", "", npm_info))
            processed_npm.add(n_idx)
        
        # Write the file
        with open(file_path, 'w') as f:
            f.write("LLVM PASS PIPELINE MAPPING VISUALIZATION\n")
            f.write("=" * 120 + "\n\n")
            
            f.write(f"LEGACY PASSES ({legacy_total} total)".ljust(60))
            f.write(f"NPM PASSES ({npm_total} total)\n")
            f.write("=" * 60 + " " * 0 + "=" * 60 + "\n\n")
            
            # Write all output lines
            for legacy_info, arrow, npm_info in output_lines:
                f.write(f"{legacy_info:<50}{arrow:<7}{npm_info}\n")
            
            # Add summary
            f.write("\n" + "=" * 120 + "\n")
            f.write("SUMMARY:\n")
            f.write(f"  Total Legacy Passes: {legacy_total}\n")
            f.write(f"  Total NPM Passes: {npm_total}\n")
            f.write(f"  Successfully Mapped: {len(mapped_pairs)}\n")
            f.write(f"  Unmapped Legacy: {len(legacy_passes) - len(mapped_legacy_indices)}\n")
            f.write(f"  Unmapped NPM: {len(npm_passes) - len(mapped_npm_indices)}\n")
            
            if divergence_result.get('divergence_found'):
                f.write(f"\nFIRST DIVERGENCE:\n")
                f.write(f"  Legacy: {divergence_result['legacy_pass'].pass_name} (#{divergence_result['legacy_pass'].pass_index})\n")
                f.write(f"  NPM: {divergence_result['npm_pass'].pass_name} (#{divergence_result['npm_pass'].pass_index})\n")
                f.write(f"  Marked with: <-D->\n")
            else:
                f.write(f"\nNO DIVERGENCE FOUND\n")
            
            f.write("\nLEGEND:\n")
            f.write("  <--->  Mapped passes with identical IR\n")
            f.write("  <-D->  First divergent pass pair\n")
            f.write("  (no arrow)  Unmapped pass\n")
        
        self.logger.info(f"Generated visualization file: {file_path}")
