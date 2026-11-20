"""Build the JP Badge Arcade offline patch for Luma3DS (first JP port build).

Adapted from the EUR builder (badge_patch.py, upstream v0.5.4). Differences:
- JP_UPDATE revision (JP address table) and JP payload source
  (patches/badge_offline_jp.s, with the story_flag / persistent_id fixes;
  v2: schedule_lookup load replay, and the boot_prepare hook remapped to
  the real JP function 0x321564; v9: badge_free_purchase is the EUR
  entry-hook form on the true purchase controller 0x30AC40, its native
  call mapped to the option->quantity getter 0x25378C — the v2-v8
  trampoline hooked the round-end controller and called mid-daily-record,
  crash3-analysis §22/§23/§24).
- v10: badge_title_resources_done calls the native APT HOME-guard release
  (canonical 0x283CE4 -> JP 0x284864, argument 1) so the HOME button works
  during ordinary play; the JP_UPDATE entry for 0x283CE4 was a stale
  un-probed EUR copy (0x28478C, mid-function in JP) and is corrected
  (crash3-analysis §27/§28). Payload-only change; hook set unchanged.
- v11: the HOME-guard ENGAGE (canonical 0x283D04 -> JP 0x284884) is hooked
  to badge_return (immediate return, no side effects) — §27 fix option 2,
  added after v10's one-shot release failed the hardware test (the guard
  is engaged after the title-resources point, or re-engaged per session
  step). JP-only hook (EXTRA_HOOKS): upstream never hooks this function.
  Pre-build audit (crash3-analysis §30): exactly 8 BL sites, all `blne`
  gated on the guard getter with argument 1, none reads the return value;
  v10's release call is kept (idempotent; covers the storage-error
  stage exit).
- v12: badge_persistent_id is relocated to the true JP ACT persistent-ID
  getter 0x29072C (canonical 0x28FBAC; resume 0x290730) and the payload
  trampoline replays the EUR-form prologue push {r3, r4, r5, r6, r7, lr}.
  The v1 table anchored it on 0x29063C, a neighbouring 2-arg ACT method,
  so the 0->1 ID substitution never reached the native save snapshot
  (0x259240) or the load account check (0x2CD7A4): the local save
  `savedata` was never written and all native SAVE state reset every
  boot — visible as the regular-machine tutorial repeating every session
  (crash3-analysis §31/§32). The hook record at 0x29063C disappears.
- badge_request_complete hook #2 (canonical 0x350718) IS included since v8:
  section 20.6/21 of work/crash3-analysis.md identified its JP target as
  0x350CEC (the play-log issue step; the EUR-mapped 0x350CE0 lands inside
  JP's longer create+start, 12 bytes before the true entry).
- The three EXPORT_SCENES "Book" string records are OMITTED in BOTH variants:
  the EUR-mapped VAs hold ARM code in the JP binary, not scene-name strings
  (JP export buttons already invoke the stock export scenes).
- --home-menu builds the HOME-Menu-export variant (crash3-analysis §25/§26):
  the 15 badge_home_* stub hooks (EUR HOME_HOOKS, filtered by canonical
  address before JP translation, EUR selected_hooks semantics) are omitted
  so the native HOME functions run stock; the payload record is identical
  to the game-only build. Output goes to code_home.ips / build_home.json.
- --home-lite builds the no-decoration release variant on the v13 lineage
  (crash3-analysis §34): of the 15 badge_home_* stubs, only the 9
  export/decoration-gating ones are applied; the 6 in HOME_KEEP_STOCK stay
  stock — the shared-extdata 0x14D1 creation chain (boot_check, mount,
  F, create helper) whose severing caused the v12 launch SD error (§33),
  the story-flag predicate (§31/§33.5), and home_result #1, isolated by
  the §34 bisection as the fresh-boot recovery gate. Output goes to
  code_v13_light.ips / build_v13_light.json.
- Vanilla stage records are included at the EUR file offsets: the JP
  instructions at those VAs were verified shape-compatible (mov r2, r8 /
  bl 0x23E404 x2 / mov r3, #0) during the port.
The assembler command defaults to clang; override with BADGE_AS
(e.g. BADGE_AS="zig cc" if clang is unavailable).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
from pathlib import Path
import subprocess
import tempfile

from patch_format import ROOT, arm_branch, encode_ips, decode_ips, read_arm_object, write_zip
from badge_versions import JP_UPDATE, Revision
from badge_patch import HOME_HOOKS, HOOKS as EUR_HOOKS

TITLE_ID = "0004000000134600"
UPDATE_TITLE_ID = "0004000e00134600"
LOAD_ADDRESS = 0x100000
PAYLOAD_ADDRESS = 0x34C7A4  # canonical (EUR 1.3.0); JP_UPDATE maps to 0x34CD78
PAYLOAD_LIMIT = 0x34D0E0    # canonical; JP_UPDATE maps to 0x34D6A8
RELEASE_VERSION = (ROOT / "VERSION").read_text().strip()

# No EUR hooks omitted (badge_request_complete #2 resolved in v8; see docstring).
OMITTED_HOOKS = {}
# JP-only extra hook (v11, crash3-analysis §27 option 2 / §30): the APT
# HOME-guard ENGAGE is made a no-op so the guard can never engage.
EXTRA_HOOKS = {0x283D04: "badge_return"}
HOOKS = {a: n for a, n in EUR_HOOKS.items() if a not in OMITTED_HOOKS}
HOOKS.update(EXTRA_HOOKS)

# crash3-analysis §33/§34: HOME_HOOKS members that must stay STOCK even in
# the no-decoration (home-lite) variant. Canonical addresses; the JP sites
# are 0x245B94 (mount / boot-chain caller), 0x25A0BC (story flag),
# 0x2646E4 (F), 0x2212DC (archive create helper), 0x3219A0 (boot check) —
# the 0x14D1 creation chain plus the story-flag predicate — and 0x245830
# (home_result #1, canonical 0x244EE4): the §34 Azahar bisection isolated
# it as the fresh-boot gate (its native recovery path — reset/unmount
# twin + re-evaluate on state 0, §29.2 — must run when the boot fork
# validates the just-created archive; the stub's fake success leaves the
# boot in the SD-error state, exactly like v12). Stubbing any of them
# reproduces the v12 launch SD error or the repeating tutorials.
HOME_KEEP_STOCK = frozenset({0x244EE4, 0x245248, 0x259680, 0x263E80, 0x2BBE04, 0x322608})


def selected_hooks(home_menu: bool = False, home_lite: bool = False,
                   extra_keep_stock: frozenset[int] = frozenset()) -> dict[int, str]:
    """EUR selected_hooks semantics: the HOME build omits the badge_home_*
    stubs (HOME_HOOKS, matched by canonical address before JP translation)
    so the native HOME-menu functions run stock (crash3-analysis §25).
    The home-lite build omits only HOME_KEEP_STOCK, so the export /
    decoration gating stubs stay applied while the 0x14D1 creation chain
    and the story-flag predicate run stock (crash3-analysis §34).
    extra_keep_stock (canonical addresses) additionally stays stock —
    used by the §34 bisection builds only."""
    omitted = HOME_HOOKS if home_menu else (
        (HOME_KEEP_STOCK | extra_keep_stock) if home_lite else frozenset())
    return {a: n for a, n in HOOKS.items() if a not in omitted}


def detect_revision(code: bytes) -> Revision:
    if len(code) == JP_UPDATE.size and hashlib.sha256(code).hexdigest() == JP_UPDATE.sha256:
        return JP_UPDATE
    raise ValueError("Unsupported executable; expected the JP 1.3.1 update decompressed .code")


def assemble_payload(revision: Revision) -> tuple[bytes, dict[str, int]]:
    with tempfile.TemporaryDirectory(prefix="badge-jp-") as temp:
        obj = Path(temp) / "badge.o"
        source = (ROOT / "patches/badge_offline_jp.s").read_text()
        filenames = re.findall(r'\.L(?:owned|profile)_[ab]:\s*\.asciz "([^"]+)"', source)
        if len(filenames) != 4 or any(len(name.encode("ascii")) > 16 for name in filenames):
            raise ValueError("Extdata backup filenames must fit the console's 16-byte name field")
        source = re.sub(r"0x[0-9a-fA-F]+", lambda m: hex(revision.address(int(m[0], 16))), source)
        assembly = Path(temp) / "badge.s"
        assembly.write_text(source)
        as_cmd = shlex.split(os.environ.get("BADGE_AS", "clang"))
        target = os.environ.get("BADGE_TARGET", "arm-none-eabi")
        cmd = [*as_cmd, "-target", target]
        march = os.environ.get("BADGE_MARCH", "armv6k" if "BADGE_AS" not in os.environ else "")
        if march:
            cmd.append(f"-march={march}")
        subprocess.run([*cmd, "-c", str(assembly), "-o", str(obj)], check=True)
        payload_address = revision.address(PAYLOAD_ADDRESS)
        payload, symbols = read_arm_object(obj.read_bytes(), payload_address)
    if len(payload) > revision.address(PAYLOAD_LIMIT) - payload_address:
        raise ValueError("Badge payload exceeds the JP NEX worker cave")
    return payload, symbols


def build_records(revision: Revision = JP_UPDATE, home_menu: bool = False,
                  home_lite: bool = False,
                  extra_keep_stock: frozenset[int] = frozenset()) -> tuple[list[tuple[int, bytes]], dict[str, int]]:
    payload, symbols = assemble_payload(revision)
    payload_address = revision.address(PAYLOAD_ADDRESS)
    records = [(payload_address - LOAD_ADDRESS, payload)]
    records.extend((revision.address(a) - LOAD_ADDRESS, arm_branch(revision.address(a), symbols[n]))
                   for a, n in selected_hooks(home_menu, home_lite, extra_keep_stock).items())
    # Default catcher vector cap: JP site verified (`mov r1, #0x1e` at 0x248770).
    records.append((revision.address(0x247E24) - LOAD_ADDRESS, bytes.fromhex("021ca0e3")))
    # Schedule heap sizes: both JP sites verified as `mov r3, #imm`
    # (0x24DE2C: #0x18000, 0x24DE08: #0x3000) -> raise to #0x40000.
    records.append((revision.address(0x24D438) - LOAD_ADDRESS, bytes.fromhex("0137a0e3")))
    records.append((0x24DE08 - LOAD_ADDRESS, bytes.fromhex("0137a0e3")))
    # Front-end resource arena size (v6, crash3-analysis §19): the JP site
    # 0x2480B8 is verified in the target binary as `mov r3, #0x380000`
    # (word 0xE3A0370E), the size argument of the 0x265024 heap-pair create
    # whose first heap backs loader-A's resource server (driver ctx
    # [task+0x24]). Activation's retained object graphs exhaust the
    # 0x380000 arena at activation #403, the loader's acquire returns 0,
    # and codec dispatch decompresses into address 0 (hardware crash #3).
    # Raise only this one call site's immediate to #0x580000
    # (word 0xE3A03716); the second 0x380000 site (0x2480F8, a different
    # subsystem's heap) is deliberately left stock.
    records.append((0x2480B8 - LOAD_ADDRESS, bytes.fromhex("1637a0e3")))
    # Vanilla stage selection: JP instructions at the EUR VAs verified
    # shape-compatible (see work/jp-build-notes.md).
    records.extend([
        (0x148FDC, bytes.fromhex("0020a0e3")),  # mov r2, #0: reuse first default schedule entry
        (0x149058, arm_branch(0x249058, symbols["badge_vanilla_stage"], link=True)),
        (0x1491C4, bytes.fromhex("0020a0e3")),  # stock catalog uses the fallback schedule
        (0x1491E4, bytes.fromhex("0130a0e3")),  # mov r3, #1: ignore its expiry date
        (0x149240, arm_branch(0x249240, symbols["badge_vanilla_stage"], link=True)),
    ])
    return sorted(records), symbols


def apply_records(code: bytes, records: list[tuple[int, bytes]], revision: Revision = JP_UPDATE) -> bytes:
    if detect_revision(code) != revision:
        raise ValueError("Unsupported executable for these patch records")
    result = bytearray(code)
    for offset, payload in records:
        if not 0 <= offset < offset + len(payload) <= len(result):
            raise ValueError("Patch record outside executable")
        result[offset:offset + len(payload)] = payload
    return bytes(result)


def verify_ips(ips: bytes, records: list[tuple[int, bytes]], revision: Revision) -> None:
    decoded = decode_ips(ips, revision.size)
    if decoded != records:
        raise ValueError("IPS round-trip mismatch")
    payload_address = revision.address(PAYLOAD_ADDRESS)
    payload_lo = payload_address - LOAD_ADDRESS
    payload_hi = payload_lo + len(records[0][1]) if records[0][0] == payload_lo else None
    for offset, data in records:
        if len(data) == 4 and offset != payload_lo:
            word = int.from_bytes(data, "little")
            if word >> 26 in (0b111010, 0b111011):  # B / BL
                disp = ((word & 0xFFFFFF) << 2) - (1 << 26) if word & 0x800000 else (word & 0xFFFFFF) << 2
                target = offset + LOAD_ADDRESS + 8 + disp
                if not (payload_address <= target < revision.address(PAYLOAD_LIMIT)):
                    raise ValueError(f"Branch at {offset + LOAD_ADDRESS:#x} targets {target:#x}, outside payload")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--code", type=Path, required=True, help="JP update decompressed .code")
    parser.add_argument("--output", type=Path, default=ROOT.parent / "out")
    variant_group = parser.add_mutually_exclusive_group()
    variant_group.add_argument("--home-menu", action="store_true",
                               help="Enable original HOME badge access; can replace custom GYTB badges")
    variant_group.add_argument("--home-lite", action="store_true",
                               help="No-decoration release variant: export stubs applied, but the "
                                    "0x14D1 creation chain and story flag stay stock (crash3-analysis §34)")
    parser.add_argument("--extra-keep-stock", default="",
                        help="Comma-separated canonical addresses to also keep stock "
                             "(home-lite bisection builds only, crash3-analysis §34)")
    args = parser.parse_args()
    extra_keep_stock = frozenset(
        int(x, 16) for x in args.extra_keep_stock.split(",") if x.strip())
    code = args.code.read_bytes()
    revision = detect_revision(code)
    hooks = selected_hooks(args.home_menu, args.home_lite, extra_keep_stock)
    records, symbols = build_records(revision, home_menu=args.home_menu,
                                     home_lite=args.home_lite,
                                     extra_keep_stock=extra_keep_stock)
    patched = apply_records(code, records, revision)
    ips = encode_ips(records, revision.size)
    verify_ips(ips, records, revision)
    args.output.mkdir(parents=True, exist_ok=True)
    stem = "home" if args.home_menu else ("v13_light" if args.home_lite else "")
    ips_name = f"code_{stem}.ips" if stem else "code.ips"
    (args.output / ips_name).write_bytes(ips)
    (args.output / (f"patched_{stem}.code.bin" if stem else "patched.code.bin")).write_bytes(patched)
    manifest = {
        "status": "v6 - front-end resource arena 0x380000 -> 0x580000 at 0x2480B8 (heap exhaustion / crash #3 fix, crash3-analysis §19); Azahar verification pending",
        "title_id": TITLE_ID,
        "update_title_id": UPDATE_TITLE_ID,
        "game_version": revision.version,
        "upstream_release_version": RELEASE_VERSION,
        "variant": "home-menu" if args.home_menu else ("home-lite" if args.home_lite else "game-only"),
        "home_menu_badges": ("enabled; native HOME export and archive access" if args.home_menu
                             else "disabled; export stubbed, stock 0x14D1 creation chain retained" if args.home_lite
                             else "disabled; collection stays inside the game"),
        "catalog_mode": "vanilla",
        "region": "JP",
        "requires_installed_update": True,
        "source_code_sha256": revision.sha256,
        "ips_sha256": hashlib.sha256(ips).hexdigest(),
        "patched_code_sha256": hashlib.sha256(patched).hexdigest(),
        "record_count": len(records),
        "hook_count": len(hooks),
        "omitted_hooks": {f"{a:#x}": n for a, n in OMITTED_HOOKS.items()},
        "omitted_home_hooks": ({f"{a:#x}": HOOKS[a] for a in sorted(HOME_HOOKS)} if args.home_menu
                               else {f"{a:#x}": HOOKS[a] for a in sorted(HOME_KEEP_STOCK)} if args.home_lite
                               else {}),
        "restubbed_home_hooks": ({f"{a:#x}": HOOKS[a] for a in sorted(HOME_HOOKS - HOME_KEEP_STOCK)}
                                 if args.home_lite else {}),
        "omitted_records": ["EXPORT_SCENES 'Book' strings x3 (EUR VAs hold code in JP)"],
        "symbols": {name: f"{addr:08x}" for name, addr in sorted(symbols.items())},
    }
    (args.output / (f"build_{stem}.json" if stem else "build.json")).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"JP Luma patch written to {args.output}/{ips_name} ({len(ips)} bytes, {len(records)} records, {len(hooks)} hooks).")


if __name__ == "__main__":
    main()
