# RSPMatch — Response Spectrum Matching Program

RSPMatch is a time-domain spectral matching tool for earthquake ground motion records, developed by **N. Abrahamson (1993)** with modifications by **Linda Al Atik (UC Berkeley, 2009)**.

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
