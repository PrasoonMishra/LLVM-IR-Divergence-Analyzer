# LLVM IR Divergence Analyzer

A tool to compare Legacy vs New Pass Manager (NPM) IR dumps and find the first point where they diverge.

## Quick Start

1. **Put your data files in the `data/` directory:**
   ```
   data/legacy.full.txt                    # Legacy pass manager dump
   data/npm.full.txt                       # NPM pass manager dump  
   data/legacy-to-npm-pass-mapping.json    # Pass mapping file
   ```

2. **Run the analyzer:**
   ```bash
   python src/main.py
   ```

## Directory Structure

```
LLVM-IR-Divergence-Analyzer/
├── src/                          # Core implementation
│   ├── main.py                   # CLI entry point
│   ├── analyzer.py              # Main analysis engine
│   ├── parser.py                # IR dump parsing (TODO)
│   ├── normalizer.py           # IR normalization (TODO)
│   └── reporter.py             # Report generation (TODO)
├── data/                        # Input data (your dumps go here)
│   ├── legacy.full.txt         # Legacy pass manager dump
│   ├── npm.full.txt            # NPM pass manager dump
│   └── legacy-to-npm-pass-mapping.json # Pass name mappings
├── config/                      # Configuration files
│   └── default_config.json     # Default settings
├── output/                      # Analysis results (auto-created)
│   ├── current/                # Latest analysis results
│   └── archive/                # Archived results
└── README.md                   # This file
```

## Usage Examples

### Basic Usage
```bash
# Use files from data/ directory
python src/main.py
```

### Custom Files
```bash
# Specify custom input files
python src/main.py --legacy my_legacy.txt --npm my_npm.txt
```

### Archive Results
```bash
# Archive results with a name
python src/main.py --archive gpu_kernel_test
```

### Configuration Options
```bash
# Auto-cleanup extracted files
python src/main.py --auto-cleanup

# Disable temp variable normalization
python src/main.py --no-ignore-temp-vars

# Quiet mode (minimal output)
python src/main.py --quiet

# Verbose mode (detailed logging)
python src/main.py --verbose
```

## How It Works

1. **Parse IR Dumps**: Extracts individual pass IR dumps from both files
2. **Create Mapping**: Maps legacy passes to NPM passes using the JSON mapping
3. **Chronological Comparison**: Compares passes in execution order
4. **Find Divergence**: Identifies first pass where IR content differs
5. **Generate Report**: Creates detailed analysis with diff output

## Expected Output

```
🔍 LLVM IR Divergence Analyzer
==================================================
📄 Legacy dump:  /home/prasmish/LLVM-IR-Divergence-Analyzer/data/legacy.full.txt
📄 NPM dump:     /home/prasmish/LLVM-IR-Divergence-Analyzer/data/npm.full.txt
🗺️  Pass mapping: /home/prasmish/LLVM-IR-Divergence-Analyzer/data/legacy-to-npm-pass-mapping.json
📁 Output dir:   output/current

🔍 Parsing IR dump files...
   Legacy passes: 171
   NPM passes: 172
🗺️  Loading pass mappings...
🔗 Creating chronological pass mapping...
⚖️  Comparing IR content...
📊 Generating analysis report...

============================================================
🎯 LLVM IR DIVERGENCE ANALYSIS RESULTS
============================================================
📊 SUMMARY:
   Legacy passes:     171
   NPM passes:        172
   Successfully mapped: 117
   Skipped passes:    51

🎯 FIRST DIVERGENCE FOUND:
   Position:      Pass pair #66
   Legacy Pass:   "phi-node-elimination" (#104 in legacy pipeline)
   NPM Pass:      "PHIEliminationPass" (#105 in NPM pipeline)

📋 LAST COMMON PASS:
   Position:      Pass pair #65
   Legacy Pass:   "si-opt-vgpr-liverange" (#103 in legacy pipeline)
   NPM Pass:      "SIOptimizeVGPRLiveRangePass" (#103 in NPM pipeline)

📁 OUTPUT FILES:
   JSON Report:   output/current/analysis/divergence_report.json
   Diff File:     output/current/analysis/first_divergence_diff.txt
   Mapping Info:  output/current/analysis/pass_mapping_used.json
   Visualization: output/current/logs/pass_mapping_visualization.txt
============================================================
```

## Configuration

Edit `config/default_config.json` to customize:
- IR normalization rules
- Output format settings
- Cleanup behavior

## Files Generated

Analysis creates:
```
output/current/
├── extracted/                   # Individual pass IR files
│   ├── legacy/001_PassName.ll
│   └── npm/001_PassName.ll  
├── analysis/
│   ├── divergence_report.json  # Detailed JSON report
│   └── first_divergence_diff.txt # Line-by-line diff
└── logs/
    └── analyzer.log            # Complete analysis log
```

## Development Status

- ✅ **Core framework**: CLI, configuration, logging
- 🔄 **In Progress**: IR parsing, normalization, reporting  
- ⏳ **Pending**: Integration testing

## Requirements

- Python 3.7+
- Standard library only (no external dependencies)
