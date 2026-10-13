# Engine movement freeze evidence

See `../../sm64-engine-movement-fix.md` for cause, changes, limitations, and reproduction commands.

`movement-fault-replays.json` records original native failures. `movement-fix-physical-wall-fault.json` preserves the intermediate board failure, which exposed the wall-standing action while frames continued advancing. `movement-fix-replays-final.json` records all 48 final native routes, including movement release. `movement-fix-physical.json` and its log contain the successful final upload, board routes, and held-reset result.

`packages/` contains the final physically tested binaries, ELF, manifest, map, and ISA audit. `baseline/` contains the earlier engine manifest; its exact binaries remain archived in `../sm64-engine-slice-001/packages/`. `source/` and `provenance/` preserve the changed source and pinned inputs. `SHA256SUMS.json` identifies the other files in this folder. No performance improvement claim is made.
