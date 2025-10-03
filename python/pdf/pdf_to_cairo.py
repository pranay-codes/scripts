#!/usr/bin/env python3
"""
Test pdftocairo (Poppler) locally:
- Verifies pdftocairo is on PATH
- Optionally prints pdfinfo for the input
- Converts one/all pages to SVG (one page at a time) into an output folder
- Lists the generated files and exits non-zero on failure

Examples:
  python test_pdftocairo.py -i "C:\\path\\plan.pdf" -o C:\\tmp\\svgs
  python test_pdftocairo.py -i ./plan.pdf -o ./out --first 1 --last 2 --verbose
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import textwrap

def run_cmd(cmd, **kw):
    """Run a command; return (rc, stdout, stderr)."""
    p = subprocess.run(cmd, capture_output=True, text=True, **kw)
    return p.returncode, p.stdout, p.stderr

def main():
    ap = argparse.ArgumentParser(
        description="Convert PDF pages to SVG using pdftocairo and list outputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Notes:
              • This drives pdftocairo one page at a time to avoid output-prefix quirks.
              • Requires Poppler (pdftocairo) on your PATH.
        """)
    )
    ap.add_argument("-i", "--input", required=True, help="Path to input PDF")
    ap.add_argument("-o", "--out", required=True, help="Output directory for SVG files")
    ap.add_argument("--first", type=int, help="First page (1-based)")
    ap.add_argument("--last",  type=int, help="Last page (1-based)")
    ap.add_argument("--no-info", action="store_true", help="Skip pdfinfo probe")
    ap.add_argument("--verbose", action="store_true", help="Print extra debug logs")
    args = ap.parse_args()

    # 0) Check pdftocairo presence
    exe = shutil.which("pdftocairo")
    if not exe:
        print("ERROR: 'pdftocairo' not found on PATH. Install Poppler and ensure its 'bin' is in PATH.", file=sys.stderr)
        return 2

    # 1) Check input PDF
    pdf = os.path.abspath(args.input)
    if not os.path.isfile(pdf):
        print(f"ERROR: PDF not found: {pdf}", file=sys.stderr)
        return 2
    size = os.path.getsize(pdf)
    if size == 0:
        print(f"ERROR: PDF is empty (0 bytes): {pdf}", file=sys.stderr)
        return 2

    # 2) Ensure output dir
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    # 3) Optional pdfinfo
    pages = None
    if not args.no_info:
        pdfinfo = shutil.which("pdfinfo")
        if pdfinfo:
            rc, so, se = run_cmd([pdfinfo, pdf])
            if args.verbose:
                print("pdfinfo output:\n" + (so or se or "").strip())
            if rc == 0 and so:
                for line in so.splitlines():
                    if line.strip().startswith("Pages:"):
                        try:
                            pages = int(line.split(":")[1])
                        except Exception:
                            pass
        elif args.verbose:
            print("pdfinfo not found; skipping info probe.")

    # 4) Decide page range
    first = args.first or 1
    last  = args.last  or (pages if pages else first)  # if pages unknown, at least do page 1
    if pages and last > pages:
        last = pages
    if args.verbose:
        print(f"Converting pages {first}..{last} (one-by-one)")
        print(f"pdftocairo exe: {exe}")
        print(f"Output dir: {out_dir}")

    # 5) Convert one page at a time
    generated = []
    for pnum in range(first, last + 1):
        out_name = f"page-{pnum:03d}.svg"    # exact output file per page
        cmd = [exe, "-svg", "-f", str(pnum), "-l", str(pnum), pdf, out_name]
        if args.verbose:
            print(f"Running: {' '.join(cmd)}  (cwd={out_dir})")
        rc, so, se = run_cmd(cmd, cwd=out_dir)
        if rc != 0:
            print(f"pdftocairo failed on page {pnum}.", file=sys.stderr)
            if se: print(se.strip(), file=sys.stderr)
            return rc
        if os.path.exists(os.path.join(out_dir, out_name)):
            generated.append(out_name)

    # 6) Validate & list results
    if not generated:
        print(f"ERROR: No SVG files generated in {out_dir}", file=sys.stderr)
        print("Directory listing:", os.listdir(out_dir), file=sys.stderr)
        return 1

    # Sort numerically in case of partial ranges
    def pnum(name): 
        try: return int(name.split("-")[1].split(".")[0])
        except: return 0
    generated.sort(key=pnum)

    print(f"OK: Generated {len(generated)} SVG file(s) in {out_dir}")
    for f in generated:
        print(" -", f)
    return 0

if __name__ == "__main__":
    sys.exit(main())
