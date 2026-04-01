from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.ifc_splitter.clustering.splitter import split_ifc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a comprehensive IFC model into isolated semantic system IFCs.",
    )
    parser.add_argument("input", type=Path, help="Path to the source IFC file.")
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path("outputs"),
        help="Directory for generated IFC subset files (default: ./output).",
    )
    parser.add_argument(
        "--proximity", "-p",
        type=float,
        default=None,
        help="Building proximity clustering threshold in metres (default: 5.0).",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    print(f"IFC Semantic Splitter")
    print(f"  Input : {args.input}")
    print(f"  Output: {args.output_dir}/\n")

    results = split_ifc(args.input, args.output_dir, args.proximity)

    print(f"\nDone — wrote {len(results)} IFC models.")


if __name__ == "__main__":

    INPUT_MODEL = Path("test_models/alchemy_2.ifc")

    if INPUT_MODEL is not None:
        output_subdir = Path("outputs") / INPUT_MODEL.stem
        sys.argv = [sys.argv[0], str(INPUT_MODEL), "--output-dir", str(output_subdir)]

    main()