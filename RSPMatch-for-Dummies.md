# RSPMatch for Dummies

## The Problem

When you design a building (especially a nuclear one), you need to prove it can survive an earthquake. To do that, you run a computer simulation — a finite element model of the building — and shake it with an earthquake.

But you can't just pick any earthquake. The NRC (or your building code) says: "Your building must survive shaking **at least this strong** at every frequency." They give you a **design spectrum** — a curve that says how much shaking the building must handle at each vibration speed (frequency).

The problem: **real earthquake recordings don't match the design spectrum.** The 1940 El Centro earthquake might be too strong at 5 Hz and too weak at 0.5 Hz compared to what the code requires.

## What "Matching" Means

RSPMatch takes a real earthquake recording and **tweaks it** so its frequency content lines up with the design spectrum.

Think of it like an audio equalizer on a stereo:
- The design spectrum says "I need this much bass, this much midrange, this much treble"
- The raw earthquake is like a song that has too much treble and not enough bass
- RSPMatch is the equalizer — it boosts the bass and tries to cut the treble until the song matches what you asked for

Except instead of sound frequencies, it's ground shaking frequencies. And instead of music, it's the ground trying to destroy a building.

## Why Not Just Use the Design Spectrum Directly?

The design spectrum is just a **smooth curve** — it's not a real time history. You can't feed a smooth curve into a structural simulation. The simulation needs an actual second-by-second recording of ground acceleration (the ground jerking back and forth for 60 seconds). RSPMatch gives you that: a realistic-looking earthquake that **also** satisfies the code requirements.

## The Files

### What goes IN

```
target.tgt          The design spectrum (the curve you're trying to match)
                    -> Comes from your seismic hazard analysis or building code

elcentro.acc        A real earthquake recording (acceleration vs time)
                    -> Comes from a database like PEER NGA

run.inp             Settings (how many iterations, what frequency range, etc.)
```

### What comes OUT

```
matched.acc         The modified earthquake record
                    -> This is what you feed into your structural model

matched.rsp         Proof that the match worked
                    -> Compare the "Target" and "Computed" columns

unmatched.rsp       The original earthquake's spectrum (for comparison)
```

## How to Read the Results

Open `matched.rsp` and look at the table at the bottom:

```
     Freq     Damping   Target   Computed   Initial
    0.2000    0.0500    1.2000    1.1999    0.0710      <- perfect match
    1.0000    0.0500    1.2000    1.2000    1.2000      <- perfect match
    5.0000    0.0500    0.2400    0.6727    1.5104      <- bad match
```

- **Target** = what you asked for
- **Computed** = what the matched record actually produces
- **Initial** = what the original earthquake had (after scaling)

**Good match:** Computed is close to Target (within a few percent)

**Bad match:** Computed is way higher than Target (usually means the original record had too much energy at that frequency)

## Why a Match Might Be Bad

RSPMatch works by **adding** small wavelets to the earthquake record to boost energy at frequencies where it's too low. It **cannot effectively remove** energy where the record is already too strong.

Imagine trying to make a loud rock song sound like a quiet jazz track using only a volume knob that goes UP. You can make the quiet parts louder, but you can't make the loud parts quieter. That's what happens when you see a bad match at high frequencies.

**The fix:** Choose a seed earthquake record whose spectrum sits **below** the target at most frequencies. That way the program only needs to add energy (which it does nearly perfectly).

## How to Pick a Good Seed Record

1. The record's spectrum should be **at or below** the target at most frequencies
2. Pick records from sites with similar geology (rock vs soil)
3. Similar magnitude and distance to what your site expects
4. Records from the PEER NGA-West2 database (https://ngawest2.berkeley.edu/) are the standard source

**Bad seed:** Original has 2g at 5 Hz, your target says 0.3g. Program can't fix this.

**Good seed:** Original has 0.1g at 5 Hz, your target says 0.3g. Program boosts it perfectly.

## How a Civil Team Would Use This

1. **Get the design spectrum** — from a PSHA (probabilistic seismic hazard analysis) or building code (ASCE 7, Reg Guide 1.208, etc.)
2. **Pick 3-7 seed earthquake records** — from PEER NGA or similar database, choosing records with similar site conditions
3. **Run each record through RSPMatch** — `./run.sh` for each one
4. **Check the results** — open each `matched.rsp` and verify Target is close to Computed
5. **Feed matched records into structural model** — ANSYS, SAP2000, LS-DYNA, SASSI, etc.
6. **Verify the building survives** — check stresses, displacements, and member forces against code limits

The NRC requires multiple matched records (not just one) because different earthquakes stress different parts of the structure differently, even if they have the same spectrum.

## Quick Reference — Running RSPMatch

```bash
# From the repo root:
cd ~/code/RSPMatch21
./run.sh

# Output goes to output/run-MM_DD_YY_HHMM/
# Each run gets its own timestamped folder
# Input files are copied into the folder so you know what produced the results
```

### To use different inputs

1. Put your target spectrum (`.tgt`) and earthquake record (`.acc`) in the `input/` directory
2. Copy and edit `input/run.inp` to point to your files (lines 17-18)
3. Run: `./run.sh` (or `./run.sh my_custom_run.inp`)

### Key parameters to adjust (in run.inp)

| Line | What it does | Rule of thumb |
|------|-------------|---------------|
| 1 | Max iterations | 80-100 for good results |
| 2 | Tolerance | 0.01 = stop if misfit drops below 1% |
| 3 | Damping (gamma) | 0.3-0.5 = stable, 0.7+ = aggressive |
| 9 | Group size | 10-15 for fine control |
| 10 | Max frequency (Hz) | Don't go above 15-20 Hz unless you need to |
| 14 | Matching freq range | Keep fmax at or below line 10 |

## Glossary

| Term | Plain English |
|------|---------------|
| **Response spectrum** | A curve showing how much a building vibrates at each frequency when shaken by an earthquake |
| **Spectral acceleration (Sa)** | How hard the ground shakes at a specific frequency, measured in g's (multiples of gravity) |
| **Design spectrum** | The code-required shaking levels your building must survive |
| **Seed record** | The real earthquake recording you start with before matching |
| **Time history** | The actual second-by-second record of ground acceleration |
| **Frequency (Hz)** | How fast something vibrates — 1 Hz = once per second, 10 Hz = 10 times per second |
| **Damping** | How quickly vibration dies out — 5% is standard for buildings |
| **PGA** | Peak Ground Acceleration — the single highest acceleration value in the record |
| **Misfit** | How far off the match is (lower = better) |
| **PSHA** | Probabilistic Seismic Hazard Analysis — the study that produces the design spectrum |
| **PEER NGA** | The main US database of earthquake recordings (Berkeley) |
| **NRC** | Nuclear Regulatory Commission — regulates nuclear facilities |
| **ASCE 7** | The standard US building code for seismic design |
| **Reg Guide 1.208** | NRC guidance on developing earthquake ground motions for nuclear plants |
