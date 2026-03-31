# Excito — Response Spectrum Matching Program

*Latin: excito — "to shake, to stir up"*

Excito is a modernized fork of RSPMatch, a time-domain spectral matching tool for earthquake ground motion records originally developed by **N. Abrahamson (1993)** with modifications by **Linda Al Atik (UC Berkeley, 2009)**.

It modifies a recorded or synthetic earthquake accelerogram so that its response spectrum matches a target design spectrum, using wavelet-based adjustment functions that preserve the non-stationary character of the original record.

**Reference:** Abrahamson, N.A. (1992). "Non-stationary spectral matching." *Seismological Research Letters*, 63(1), 30.

## Building

### Prerequisites

- **gfortran** (GNU Fortran compiler, part of GCC)

```bash
# Ubuntu/Debian
sudo apt install gfortran

# macOS (via Homebrew)
brew install gcc

# RHEL/CentOS
sudo yum install gcc-gfortran
```

### Compile

```bash
cd "RSPMatch99_Sub Files"
gfortran -ffixed-line-length-none -std=legacy -o rspmatch \
  Acc_Mod.F Baseline.F C_Matrix.F Filter.F Input.F Integ_Funcs.F \
  Match.F Math.F Output.F PGA_Funcs.F Response.F Target.F RSPM09.F
```

**Important flags:**
- `-ffixed-line-length-none` — Required. The header file `rspMatch.h` has a `parameter` statement that exceeds the Fortran 77 column limit (72 characters).
- `-std=legacy` — Required. Suppresses errors for deprecated `PAUSE` statements and shared DO termination labels.

**Do NOT compile `RSPM99.F`** — it is a monolithic copy of all subroutines and will cause duplicate symbol errors if compiled alongside the modular `.F` files. The main program is `RSPM09.F`.

### Compiler warnings

You will see warnings about array bounds and deleted Fortran features. These are expected for legacy Fortran 77 code using assumed-size arrays and are harmless at runtime.

### Runtime floating-point messages

When running, you may see:

```
Note: The following floating-point exceptions are signalling: IEEE_DIVIDE_BY_ZERO IEEE_UNDERFLOW_FLAG IEEE_DENORMAL
```

This is normal. It means the numerical routines encountered division by zero, extremely small numbers, or denormalized floats during matrix operations (SVD, eigenvalue checks). The program handles all of these internally with eigenvalue cutoffs and convergence checks. The results are correct. To suppress the message, add `-ffpe-summary=none` to the compile command.

## Running

RSPMatch reads from stdin. It expects the path to a **master input file** which lists run configurations:

```bash
echo master.inp | ./rspmatch
```

### Input File Structure

RSPMatch uses a three-level input file hierarchy:

```
master.inp          ← lists how many runs and which run files
  └── run.inp       ← parameters + paths to data files
        ├── target.tgt    ← target response spectrum
        └── elcentro.acc  ← input accelerogram
```

#### 1. Master Input File (`master.inp`)

```
1                   <- number of runs
run.inp             <- path to run parameter file
```

You can list multiple run files for batch processing.

#### 2. Run Parameter File (`run.inp`)

One value per line, read in this exact order:

```
30                          # max iterations (eg 30)
0.02                        # tolerance for spectral match (eg 0.02)
0.5                         # convergence damping gamma (eg 0.5)
7                           # model: 1=reverse impulse, 6=tapered cosine, 7=improved tapered cosine
1.0 1.0 0.1 25.0           # alpha model parameters (a1, a2, f1, f2)
1 1.0                       # scaleFlag scalePeriod (0=no scale, 1=PGA, 2=at period)
1                           # interpolation flag (1=no interpolation, >1=interpolation factor)
1.0e-5                      # minimum eigenvalue (eg 1.0e-5)
20                          # group size for subgroup iterations (eg 20)
25.0                        # max frequency in Hz
0.1 25.0 4                  # initial bandpass filter: fmin(Hz) fmax(Hz) nPoles
0                           # modify PGA? (0=no, 1=yes)
0 0.0                       # randomize target? (0=no) randomFactor
0.1 25.0                    # frequency band for matching: fmin fmax (Hz)
1                           # baseline correction flag (0=no, 1=yes)
1.0                         # scale factor
target.tgt                  # target spectrum file path
elcentro.acc                # input accelerogram file path
matched.acc                 # output: matched accelerogram
matched.rsp                 # output: matched response spectrum
unmatched.rsp               # output: unmatched (original) response spectrum
```

#### 3. Target Spectrum File (`target.tgt`)

```
Title line (up to 80 characters)
nFreq  nDamp
damp1  [damp2  ...]                          <- damping ratio(s)
freq1  minTime1  maxTime1  Sa1  [Sa2  ...]   <- Hz, seconds, seconds, g
freq2  minTime2  maxTime2  Sa1  [Sa2  ...]
...
```

- **freq**: frequency in Hz
- **minTime / maxTime**: time window for wavelet adjustment (use `0.0` and `1000.0` to cover full record)
- **Sa**: target spectral acceleration in g (one column per damping ratio)

#### 4. Accelerogram File (`elcentro.acc`)

```
Title line (up to 80 characters)
nPts  dt  nAdded
acc1  acc2  acc3  ...
```

- **nPts**: number of acceleration data points
- **dt**: time step in seconds
- **nAdded**: number of zero-padded points at start (0 for unpadded records)
- **acc**: acceleration values in **g** (free format, can be multiple values per line)

## Sample Data

The `input/` directory contains ready-to-run test data:

| File | Description |
|------|-------------|
| `input/master.inp` | Master input (1 run) |
| `input/run.inp` | Parameters: 80 iterations, model 7, 0.2-15 Hz, 5% damping |
| `input/target.tgt` | ASCE 7-22 design spectrum (Site Class D, Ss=1.5g, S1=0.6g) |
| `input/elcentro.acc` | El Centro 1940 NS component (2688 pts, dt=0.02s) |

### Run the example

The easiest way to run is with the included `run.sh` script:

```bash
./run.sh
```

This creates a timestamped output directory (e.g. `output/run-03_27_26_1542/`) containing:
- `matched.acc` — spectrum-matched accelerogram
- `matched.rsp` — response spectrum of matched record
- `unmatched.rsp` — response spectrum of original record
- `run.inp` — copy of the parameters used
- `target.tgt` — copy of the target spectrum used
- `elcentro.acc` — copy of the input accelerogram used
- `log.txt` — full program output

Each run gets its own directory, so previous results are never overwritten.

### Using different inputs

By default, `run.sh` uses `input/run.inp`. To use a different configuration:

```bash
# Create a new run file
cp input/run.inp input/run_tight.inp
# Edit parameters as needed, then run:
./run.sh run_tight.inp
```

All run files and data files (`.tgt`, `.acc`) should be placed in the `input/` directory.

### Running manually (without the script)

You can also run RSPMatch directly from the `input/` directory:

```bash
cd input
echo master.inp | "../RSPMatch99_Sub Files/rspmatch"
```

Output files will be written to the current directory.

### Expected output

The program iterates, showing convergence of average and maximum misfit:

```
Initial Solution    AveMisfit  MaxMisfit  ...
                      2.0586     6.7770
...
     80 full set      1.4801    10.2103   15.008  0.050  0.540
```

### Tips for better convergence

| Parameter | Conservative | Aggressive | Notes |
|-----------|-------------|------------|-------|
| Max iterations | 80-100 | 30 | More = better match, slower |
| Gamma (damping) | 0.3-0.4 | 0.7-1.0 | Lower = steadier convergence |
| Max frequency | 15 Hz | 25 Hz | High frequencies are hardest to match |
| Group size | 10-15 | 20-30 | Smaller = finer corrections |
| Tolerance | 0.01 | 0.05 | Stops early if reached |

## Verifying Results

The `.rsp` output files contain a table comparing **Target** vs **Computed** spectral acceleration at each frequency. Open `matched.rsp` and look at these columns:

```
     Freq     Damping   Target   Computed   Initial  Randomized  tPeak
    0.2000    0.0500    1.2000    1.1999    0.0710    1.2000   44.0600
    1.0000    0.0500    1.2000    1.2000    1.2000    1.2000   13.1500
```

**How to read it:**
- **Target** = what you asked for (from your `.tgt` file)
- **Computed** = what the matched record actually produces
- **Initial** = what the original (scaled) record had before matching

**The match is good when** Computed ≈ Target (within a few percent). Perfect matches show 0.0% difference.

**The match will be poor when** the Initial spectrum is much higher than the Target. RSPMatch works by adding wavelets — it can boost energy at frequencies where the record is too weak, but it cannot effectively remove energy where the record is too strong. If you see large mismatches at high frequencies, it usually means your seed record has too much high-frequency content relative to the target.

**Choosing a good seed record:**
- Pick a record whose spectrum is **at or below** the target at most frequencies
- Records from similar site conditions (soil type, distance, magnitude) work best
- If the initial spectrum is 2-3x above the target at many frequencies, the matching will struggle

## Source Files

| File | Purpose |
|------|---------|
| `RSPM09.F` | Main program (Version 2009) |
| `RSPM99.F` | Monolithic version (all subroutines in one file — do not compile with other `.F` files) |
| `Input.F` | Input file readers (parameters, target spectrum, accelerogram) |
| `Output.F` | Output writers |
| `Match.F` | Spectral matching algorithm |
| `Response.F` | Response spectrum calculation |
| `C_Matrix.F` | C-matrix and alpha computation |
| `Filter.F` | FFT-based filtering (bandpass, lowpass, highpass) |
| `Math.F` | Linear algebra (SVD, OLS, matrix inversion, RNG) |
| `Baseline.F` | Baseline correction |
| `Acc_Mod.F` | Acceleration modification functions |
| `Target.F` | Target spectrum utilities (randomization, subdivision) |
| `PGA_Funcs.F` | PGA computation functions |
| `Integ_Funcs.F` | Numerical integration |
| `rspMatch.h` | Header with array dimension parameters |

## Models

The `iModel` parameter selects the wavelet adjustment function:

| Value | Model | Description |
|-------|-------|-------------|
| 1 | Reverse impulse response | Original Abrahamson (1993) |
| 6 | Tapered cosine | Improved stability |
| 7 | Improved tapered cosine | **Recommended** — Al Atik (2009), best convergence and drift prevention |

## License

Original code by N. Abrahamson, copyright 1993. Modified by Linda Al Atik, UC Berkeley, 2009.

## Known Limitations & Seed Selection

### The sample data caveat

The included El Centro 1940 record is a classic textbook earthquake but a **poor seed choice** for a steeply-falling ASCE 7 design spectrum. After scaling to match the low-frequency plateau, El Centro has 5-10x more energy than the target above 3 Hz. While the algorithm does subtract energy at high frequencies (the matched record is visibly lower amplitude than the original), it cannot remove enough to track a steeply falling target.

With the included sample data, expect:
- **0.2-2.5 Hz: near-perfect match** (< 1% misfit)
- **3-15 Hz: significant overshoot** (the matched spectrum flatlines around 0.4g instead of following the target down)

This is a seed selection problem, not an algorithm problem.

### How the algorithm handles overshoot

RSPMatch adds signed adjustment wavelets to the acceleration record. These wavelets can be positive or negative — the algorithm can both increase and decrease spectral ordinates. However, convergence at a given frequency is limited by the `maxDeltaR` parameter in `Match.F` (set to 0.1, meaning each iteration can adjust a spectral ordinate by at most 10% of its current value). When the seed overshoots the target by 500-1000%, this cap makes convergence extremely slow.

Additionally, wavelets added at low frequencies generate spectral leakage at higher frequencies, creating a "floor" that the algorithm struggles to push below.

### Choosing a good seed record

For production work, seed selection is critical. The algorithm converges quickly and accurately when the seed spectrum sits **at or below** the target at most frequencies.

**Guidelines:**
- Pick records whose spectral shape naturally resembles your target — less work for the matching algorithm
- For steeply-falling targets (ASCE 7, NRC Reg Guide 1.60), use seeds with less high-frequency energy: larger magnitude events, longer source-to-site distances, or soft-soil recordings
- Avoid near-fault records with broadband flat spectra (like El Centro) when your target drops off steeply past the plateau
- Use 3-7 different seed records per project — different earthquakes stress different parts of a structure even with the same spectrum

### PEER NGA Database

The standard source for seed records is the PEER NGA (Pacific Earthquake Engineering Research Center) ground motion database:

- **NGA-West2** (https://ngawest2.berkeley.edu/) — ~8,600 records from 334 shallow crustal events (M3.4-7.9). Use for active tectonic regions (western US).
- **NGA-East** — 27,000+ records from Central and Eastern North America. Use for stable continental regions (eastern US).

The web tool lets you filter by magnitude, distance, Vs30 (site class), and fault type. For seed selection, filter for records with spectral shapes that naturally resemble your target spectrum.

### Multi-pass matching

For difficult seed-target combinations, a multi-pass approach with progressively widening frequency bands improves convergence. See the `multipass-experiments` branch for scripts and examples. Typical strategy:

1. Pass 1: Match low frequencies only (0.2-1.5 Hz)
2. Pass 2: Widen to 0.2-3 Hz
3. Pass 3: Widen to 0.2-7 Hz
4. Pass 4-5: Full band (0.2-15 Hz) with lower gamma for polish

This is the approach used by commercial tools like RspMatchEDT, which automates the multi-pass staging and parameter selection.


### How to download seed records from PEER NGA

1. **Create a free account** at https://ngawest2.berkeley.edu/
2. **Search for records** using the search tool:
   - Set magnitude range (e.g. 6.0-7.5)
   - Set distance range (e.g. 10-50 km)
   - Set Vs30 range to match your site class (e.g. 180-360 m/s for Site Class D)
   - Optionally filter by fault type (strike-slip, reverse, etc.)
3. **Download** — select records and download as `.AT2` files (text format)

#### Converting PEER AT2 format to RSPMatch format

PEER `.AT2` files look like this:

```
PEER NGA STRONG MOTION DATABASE RECORD
Imperial Valley-06, 10/15/1979, El Centro Array #12, 140
ACCELERATION TIME SERIES IN UNITS OF G
NPTS=  7814, DT= .0050 SEC,
  3.654112E-04  3.647600E-04  3.640805E-04  3.633667E-04  3.626163E-04
  ...
```

RSPMatch `.acc` files need this format:

```
Title line
nPts  dt  nAdded
acc1  acc2  acc3  ...
```

To convert, extract `NPTS` and `DT` from line 4 of the AT2 file, write them as line 2, and copy all the acceleration values after line 4. A simple conversion script is included in the repo:

```bash
# Convert PEER AT2 to RSPMatch acc format
./convert_at2.sh record.AT2 record.acc
```

Or manually:

```bash
# Line 1: title (from AT2 line 2)
sed -n '2p' record.AT2 > record.acc

# Line 2: npts dt nadded (parsed from AT2 line 4)
NPTS=$(sed -n '4p' record.AT2 | grep -oP 'NPTS=\s*\K[0-9]+')
DT=$(sed -n '4p' record.AT2 | grep -oP 'DT=\s*\K[.0-9]+')
echo "$NPTS $DT 0" >> record.acc

# Remaining lines: acceleration data
tail -n +5 record.AT2 >> record.acc
```

Then place the `.acc` file in `input/` and update line 18 of your `run.inp` to point to it.

#### Tips for picking good seeds

- **Look at the spectral shape**, not just magnitude/distance. PEER shows response spectra for each record — pick ones whose shape drops off similarly to your target above the plateau.
- **Pick records that sit below the target.** The algorithm boosts energy efficiently but struggles to remove large amounts. A seed at 50-80% of the target across all frequencies is ideal.
- **Avoid broadband flat spectra** (like near-fault records) when your target drops steeply. Choose records from moderate distances or soft-soil sites that naturally roll off at high frequencies.
- **Download multiple records.** Building codes typically require 3-7 matched time histories per analysis.
