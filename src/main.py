#!/usr/bin/env python3
"""
LLVM IR Divergence Analyzer
Compares Legacy vs NPM pass pipeline IR dumps to find first divergence point.

Usage:
    python main.py                                    # Use default data/ files
    python main.py --legacy legacy.txt --npm npm.txt # Specify custom files
    python main.py --help                            # Show full help
"""

import argparse
import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from data_types import ComparisonConfig
from analyzer import IRDivergenceAnalyzer


def load_default_config() -> Dict[str, Any]:
    """Load default configuration from config file"""
    config_file = Path(__file__).parent.parent / "config" / "default_config.json"
    
    if config_file.exists():
        with open(config_file, 'r') as f:
            return json.load(f)
    
    # Fallback default config
    return {
        "ignore_whitespace": True,
        "ignore_empty_lines": True,
        "ignore_temp_vars": True,
        "ignore_labels": True,
        "ignore_metadata": True,
        "ignore_debug_info": True,
        "ignore_comments": False,
        "auto_cleanup": False
    }


def create_cli_parser() -> argparse.ArgumentParser:
    """Create comprehensive CLI argument parser"""
    
    parser = argparse.ArgumentParser(
        description="LLVM IR Divergence Analyzer - Find where Legacy and NPM pipelines diverge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default files from data/ directory
  python main.py
  
  # Specify custom input files  
  python main.py --legacy my_legacy.txt --npm my_npm.txt
  
  # Use custom mapping file
  python main.py --mapping custom_mapping.json
  
  # Enable auto-cleanup after analysis
  python main.py --auto-cleanup
  
  # Customize normalization (disable temp var normalization)
  python main.py --no-ignore-temp-vars
  
  # Archive results with custom name
  python main.py --archive testcase_gpu_kernel
        """)
    
    # Input files
    parser.add_argument(
        "--legacy", 
        type=str, 
        default=None,
        help="Legacy pass manager dump file (default: data/legacy.full.txt)"
    )
    
    parser.add_argument(
        "--npm", 
        type=str, 
        default=None, 
        help="New pass manager dump file (default: data/npm.full.txt)"
    )
    
    parser.add_argument(
        "--mapping", 
        type=str, 
        default=None,
        help="Legacy-to-NPM pass mapping JSON file (default: data/legacy-to-npm-pass-mapping.json)"
    )
    
    # Output options
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="output/current",
        help="Output directory for analysis results (default: output/current)"
    )
    
    parser.add_argument(
        "--archive", 
        type=str, 
        default=None,
        help="Archive results with given name (saved to output/archive/<name>_<date>/)"
    )
    
    parser.add_argument(
        "--no-cleanup", 
        action="store_true",
        help="Skip cleanup at start (no prompt)"
    )
    
    parser.add_argument(
        "--clean", 
        action="store_true",
        help="Only clean up previous results and exit (don't run analysis)"
    )

    # Normalization options
    parser.add_argument(
        "--no-ignore-temp-vars", 
        action="store_true",
        help="Don't normalize temporary variable names"
    )
    
    parser.add_argument(
        "--no-ignore-labels", 
        action="store_true", 
        help="Don't normalize basic block label names"
    )
    
    parser.add_argument(
        "--no-ignore-metadata", 
        action="store_true",
        help="Don't ignore metadata lines (starting with !)"
    )
    
    parser.add_argument(
        "--ignore-comments", 
        action="store_true",
        help="Ignore comment lines (starting with ;)"
    )
    
    # Verbosity
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Enable verbose terminal output"
    )
    
    parser.add_argument(
        "--quiet", "-q", 
        action="store_true", 
        help="Minimal terminal output (errors only)"
    )
    
    return parser


def resolve_file_paths(args) -> tuple:
    """Resolve input file paths with defaults"""
    
    data_dir = Path(__file__).parent.parent / "data"
    
    # Default file paths
    legacy_file = args.legacy or (data_dir / "legacy.full.txt")
    npm_file = args.npm or (data_dir / "npm.full.txt") 
    mapping_file = args.mapping or (data_dir / "legacy-to-npm-pass-mapping.json")
    
    # Validate files exist
    for name, path in [("Legacy", legacy_file), ("NPM", npm_file), ("Mapping", mapping_file)]:
        if not Path(path).exists():
            print(f" Error: {name} file not found: {path}")
            if not args.legacy and name == "Legacy":
                print(" Tip: Create data/legacy.full.txt or use --legacy flag")
            sys.exit(1)
    
    return str(legacy_file), str(npm_file), str(mapping_file)


def create_comparison_config(args, default_config: Dict) -> ComparisonConfig:
    """Create ComparisonConfig from CLI args and defaults"""
    
    # Load excluded passes from config
    excluded_passes = default_config.get("excluded_passes", {})
    excluded_legacy = excluded_passes.get("legacy_passes", [])
    excluded_npm = excluded_passes.get("npm_passes", [])
    
    return ComparisonConfig(
        ignore_whitespace=default_config.get("ignore_whitespace", True),
        ignore_empty_lines=default_config.get("ignore_empty_lines", True),  
        ignore_temp_vars=not args.no_ignore_temp_vars and default_config.get("ignore_temp_vars", True),
        ignore_labels=not args.no_ignore_labels and default_config.get("ignore_labels", True),
        ignore_metadata=not args.no_ignore_metadata and default_config.get("ignore_metadata", True),
        ignore_debug_info=default_config.get("ignore_debug_info", True),
        ignore_comments=args.ignore_comments or default_config.get("ignore_comments", False),
        verbose=args.verbose,
        quiet=args.quiet,
        excluded_legacy_passes=excluded_legacy,
        excluded_npm_passes=excluded_npm
    )


def handle_cleanup_at_start(args, output_dir: str):
    """Handle cleanup at start of analysis"""
    import shutil
    
    output_path = Path(output_dir)
    extracted_dir = output_path / "extracted"
    
    # Check if there's anything to clean up
    if not extracted_dir.exists() or not any(extracted_dir.iterdir()):
        return  # Nothing to clean up
    
    should_cleanup = False
    
    if args.no_cleanup:
        should_cleanup = False
        print("Skipping cleanup (--no-cleanup specified)")
    else:
        # Interactive prompt
        try:
            response = input("Clean up previous results? (y/N): ").strip().lower()
            should_cleanup = response in ['y', 'yes']
        except (EOFError, KeyboardInterrupt):
            should_cleanup = False
    
    if should_cleanup:
        try:
            if extracted_dir.exists():
                shutil.rmtree(extracted_dir)
            analysis_dir = output_path / "analysis"
            if analysis_dir.exists():
                shutil.rmtree(analysis_dir)
            logs_dir = output_path / "logs"
            if logs_dir.exists():
                shutil.rmtree(logs_dir)
            print("Cleanup completed")
        except Exception as e:
            print(f"Cleanup error: {e}")
    else:
        print("Keeping previous results")


def setup_output_directory(args) -> str:
    """Setup output directory, handle archiving"""
    
    if args.archive:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = f"output/archive/{args.archive}_{timestamp}"
        print(f"Archiving results to: {output_dir}")
    else:
        output_dir = args.output_dir
        print(f"Output directory: {output_dir}")
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    return output_dir


def main():
    """Main CLI entry point"""
    
    parser = create_cli_parser()
    args = parser.parse_args()
    
    # Load configuration
    default_config = load_default_config()
    
    # Resolve file paths
    legacy_file, npm_file, mapping_file = resolve_file_paths(args)
    
    # Setup output
    output_dir = setup_output_directory(args)
    
    # Handle cleanup at start
    handle_cleanup_at_start(args, output_dir)
    
    # Create config
    config = create_comparison_config(args, default_config)

    # Add this check to exit after cleanup
    if args.clean:
        if not config.quiet:
            print("Exiting.")
        return 0
    
    if not config.quiet:
        print("LLVM IR Divergence Analyzer")
        print("=" * 50)
        print(f"Legacy dump:  {legacy_file}")
        print(f"NPM dump:     {npm_file}")
        print(f"Pass mapping: {mapping_file}")
        print(f"Output dir:   {output_dir}")
        print()
    
    try:
        # Create and run analyzer
        analyzer = IRDivergenceAnalyzer(
            legacy_file=legacy_file,
            npm_file=npm_file, 
            mapping_file=mapping_file,
            output_dir=output_dir,
            config=config
        )
        
        # Run analysis
        result = analyzer.analyze_divergence()
        
        # Print results
        if not config.quiet:
            analyzer.print_summary(result)
        
        return 0 if result.get('success', False) else 1
        
    except KeyboardInterrupt:
        print("\n  Analysis interrupted by user")
        return 130
    except Exception as e:
        print(f" Fatal error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
