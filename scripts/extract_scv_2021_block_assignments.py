#!/usr/bin/env python3
"""Extract the three official SCV 2021 plans into one compact tracked table."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import pandas as pd


MEMBERS = {
    "cd": "SCV Final 2021 Redistricting Plans/SCV FINAL CD Blkassign.txt",
    "state_house": "SCV Final 2021 Redistricting Plans/SCV FINAL HOD blkassign.txt",
    "state_senate": "SCV Final 2021 Redistricting Plans/SCV FINAL SD blkassign.txt",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Data/scv_2021_block_assignments.csv.gz"),
    )
    args = parser.parse_args()

    frames = []
    with zipfile.ZipFile(args.source_zip, "r") as archive:
        for column, member in MEMBERS.items():
            with archive.open(member) as source:
                frame = pd.read_csv(
                    source,
                    header=None,
                    names=["block_geoid20", column],
                    dtype=str,
                    skipinitialspace=True,
                )
            frame["block_geoid20"] = frame["block_geoid20"].str.strip().str.zfill(15)
            frame[column] = frame[column].str.strip()
            frames.append(frame)

    merged = frames[0]
    for frame in frames[1:]:
        merged = merged.merge(frame, on="block_geoid20", how="outer", validate="one_to_one")
    merged = merged.sort_values("block_geoid20")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(
        args.output,
        index=False,
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )
    print(f"Wrote {len(merged)} block assignments to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
