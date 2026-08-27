# Skill Observation Log

Observations captured during task-oriented work. Each entry identifies a
potential skill improvement or new skill opportunity.

**Status key:** OPEN = not yet actioned | ACTIONED = skill updated/created |
DECLINED = user decided not to pursue

---

## 2026-08-06 — Penrose 600 Hybrid IDEX variant

### Observation 1: Merging two hardware variants requires an explicit conflict hunt, not just two independent surveys
**Status:** OPEN

**Date:** 2026-08-06
**Session context:** Creating a new printer SKU that combines an IDEX dual-pellet
machine (branch A) with a CAN filament extruder head (branch B) in an embedded
3D-printer control codebase.
**Skill:** New skill candidate: merging-hardware-variants (or an addition to any
codebase-exploration skill)
**Type:** open-source
**Phase/Area:** Exploration / planning phase

**Issue:** Three parallel exploration agents were dispatched: one per source
branch plus one for upstream references. Each returned an accurate description
of its own branch. The decisive finding — that branch B assigned the filament
runout switch to a pin (PF3) which branch A uses as the second carriage's X
endstop — only surfaced because one agent's brief happened to ask "what
conflicts will I hit merging these?" rather than only "how does this work?".
Had that framing been missing, the conflict would have reached hardware: the
config parses fine, and the failure mode is a homing fault, not a config error.
A second conflict of the same class (a motion-sync target that had to change
from `extruder` to `extruder1`) was caught by the same framing.

**Suggested improvement:** When a task is "combine variant A and variant B",
add an explicit conflict-inventory step to the exploration phase, dispatched
as its own agent brief or as a required section in each agent's brief: enumerate
every shared resource (pins, addresses, slots, section names, filenames,
identifiers) that both sources claim, and report the overlaps as a table. Treat
resource-level collisions as first-class findings, not as a subsection of
"here's how it works".

**Principle:** A merge is not the union of two descriptions. Understanding each
source completely is necessary but not sufficient — the failure modes of a merge
live in the *intersection*, which no single-source survey is looking at. When
work involves combining two things, make "what do these two both claim?" a
separate question with its own answer, because it is nobody's job otherwise.

### Observation 2: Ship unknown external values as fail-safe, greppable placeholders rather than blocking or guessing
**Status:** OPEN

**Date:** 2026-08-06
**Session context:** Two hardware sensor pin assignments were not yet known; the
user explicitly asked for placeholders so implementation could proceed.
**Skill:** New skill candidate: placeholder-values-for-unknown-externals
**Type:** open-source
**Phase/Area:** Implementation, when a dependency value is pending

**Issue:** Two config values depended on physical wiring the user had not yet
determined. Three options existed: block on the answer, guess and hope, or omit
the sections. All three are bad — blocking stalls a day of work, guessing ships
a plausible-looking wrong value that nobody re-checks, and omitting means the
dependent code paths can't be written or tested at all. What worked instead was
a three-part convention: (a) a plausible value so the system still loads and all
dependent code is exercisable, (b) the runtime behaviour set to its *safe*
setting rather than its intended one, so a wrong value cannot cause harm, and
(c) a distinctive greppable marker on every affected line plus the documented
grep command, so the follow-up is a mechanical audit rather than a memory test.
The verification step then asserted the marker count matched expectation.

**Suggested improvement:** Codify the pattern for any skill covering
implementation under incomplete information: placeholder value + fail-safe
runtime setting + unique greppable marker + documented retrieval command +
a count assertion in the verification step. Explicitly note that the fail-safe
setting is the part most often skipped, and it is the part that prevents harm.

**Principle:** "TODO" is a note to a person who will not read it. A placeholder
becomes safe to ship when the wrong value cannot cause damage and the right
value can be found by a command rather than by remembering. Unknown-but-pending
is a normal state; the discipline is making it *auditable* instead of making it
invisible.

### Observation 3: Code that rewrites user-owned config files should be verified by round-trip, not single-pass
**Status:** OPEN

**Date:** 2026-08-06
**Session context:** Implementing logic that comments/uncomments a hardware
block inside a config file the operator also hand-edits (they paste a hardware
UUID into it), across printer-variant switches and firmware updates.
**Skill:** New skill candidate: verifying-config-file-mutators
**Type:** open-source
**Phase/Area:** Verification

**Issue:** The mutation logic looked obviously correct when read, and a
single-pass test (apply once, inspect output) passed. The real risk was not in
one pass but in the cycle: the operator's hand-entered value had to survive
enable → disable → re-enable, and the machine's own auto-generated calibration
tail had to survive the same. Writing the test as a full round trip with
assertions on the *user's* data (not the tool's own output) was what actually
established the behaviour, and it also caught that a legacy file lacking the
block entirely needed an insert path rather than a no-op.

**Suggested improvement:** For any code that edits a file a human or another
program also writes, make the verification step a round trip by default:
apply → inject a foreign value → apply the inverse → apply again → assert the
foreign value and any third-party content are byte-identical. Assert on the
data you do not own, not on the data you produced.

**Principle:** Config files are shared ownership. Correctness for a mutator is
not "did my change land" but "did everyone else's data survive my change, N
times over". Single-pass tests only ever check the first half of that.

## 2026-08-27 — Penrose 600 Hybrid: config-swap rework

### Observation 4: A comment asserting a hardware fact is not evidence
**Status:** OPEN

**Date:** 2026-08-27
**Session context:** Reworking an IDEX printer config; deciding whether bed
levelling could run with either of two extruders.
**Skill:** New skill candidate: verifying-hardware-claims-in-code
**Type:** open-source
**Phase/Area:** Investigation, whenever code describes physical reality

**Issue:** A config comment read "the T1 filament head has no probe wired to
PD8". I reasoned from it confidently across two exchanges — including
building a detailed argument that an entire architecture change was
unnecessary *because* of it. The comment was false: the probe is bed-side and
either nozzle can trigger it. The decisive counter-evidence was already in
the repo — the sibling dual-carriage machine probes with whichever carriage
is active, using a byte-identical `[probe]` section — but I did not look for
it until the user pushed back twice. I had treated a comment as a
specification.

**Suggested improvement:** When code comments describe hardware (a sensor's
location, what a pin is wired to, what a mechanism can physically do), treat
them as the least reliable content in the file: they were true at some point,
about some machine, and nothing fails when they rot. Before reasoning from
one, cross-check it against a sibling config, the hardware, or the user.
Cheapest reliable move: diff the claim against how the *other* variants
configure the same component.

**Principle:** Comments about software can be checked against the software.
Comments about hardware cannot be checked by reading harder — they need an
external source. Confidence should be capped by the quality of that source,
not by how clearly the comment is written.

### Observation 5: Restructuring silently drops what the old structure enforced for you
**Status:** OPEN

**Date:** 2026-08-27
**Session context:** Replacing a framework construct (Klipper's
`[dual_carriage]`) with two hand-rolled single-carriage configurations.
**Skill:** New skill candidate: replacing-framework-constructs
**Type:** open-source
**Phase/Area:** Design and implementation of structural refactors

**Issue:** Every explicit value carried over correctly — pins, endstops,
travel limits, verified parameter-by-parameter. What did *not* carry over
were the things the construct had been doing implicitly: a `safe_distance`
that the framework enforced on every move (nothing replaced it, leaving a
collision guard weaker than before), and per-tool offsets that were applied
on tool activation (in the new model there was no tool activation, so every
print in one mode would have been shifted). Neither was in the section I was
migrating; both only surfaced when the user asked whether kinematics had been
considered.

**Suggested improvement:** When replacing a framework construct, build two
inventories, not one: (a) the configuration it held — which diffing catches —
and (b) the *behaviours* it provided, which diffing cannot catch because they
were never written in the config. Source (b) from the framework's docs for
that construct, and from every call site that relied on it. Treat each
behaviour as needing an explicit replacement or an explicit decision to drop.

**Principle:** A refactor's risk is not in the lines you move. It is in the
guarantees you stop receiving without ever having written them down.

### Observation 6: "Set position" is not "know position"
**Status:** OPEN

**Date:** 2026-08-27
**Session context:** A parked motion axis, held outside the kinematic system.
**Skill:** New skill candidate: verifying-hardware-claims-in-code (same skill)
**Type:** open-source
**Phase/Area:** Implementation and review of state-establishing code

**Issue:** The code called `SET_POSITION=0` on a parked carriage and I
documented it as "homed and parked". `SET_POSITION` *declares* a coordinate —
it neither moves the axis nor measures anything. The comment claiming a home
had happened survived several of my own review passes, because the code
*looked* like homing: it named a stepper, it named a position, it ran at
startup. The real fix needed an endstop and an actual seek move.

**Suggested improvement:** In any state-establishing code, separate APIs that
*assert* state from APIs that *establish* it, and never describe the former
with verbs implying the latter ("homed", "verified", "calibrated",
"synced"). During review, ask of each such call: what physical or observable
event would have to occur for this to be false, and would anything notice?

**Principle:** An assertion API inherits the confidence of the assumption
behind it and none of the authority its name implies — and it reads like
verification to the next person, including a later you.

### Observation 7: Config that lives only on the device is config that is already being destroyed
**Status:** OPEN

**Date:** 2026-08-27
**Session context:** A calibrated sensor table that existed on machines but
was not in the repository.
**Skill:** New skill candidate: deploy-overwrite-audit
**Type:** open-source
**Phase/Area:** Deployment, whenever a deploy regenerates files

**Issue:** The user asked whether a custom thermistor table was still in use.
It was nowhere in version control — not in any branch or any commit. It
existed only on the machines. Because the deploy path rewrites the target
file from a template and preserves only two specific blocks, that table had
been silently wiped by every firmware update. The user's instinct ("I think
it might have gotten overridden somewhere") was exactly right, and the
mechanism was in code I had already read without connecting it.

**Suggested improvement:** For any deploy that regenerates rather than patches
a file, write down the preserve-list explicitly, then ask what real
deployments are likely to have added outside it. Anything found is either
promoted into version control or documented as deliberately ephemeral.
Do this when first touching the deploy path, not when someone notices data
missing.

**Principle:** "It works on the machine" and "it is in the repo" are
independent facts. Where a deploy overwrites, the gap between them is not a
tidiness problem — it is a countdown.
