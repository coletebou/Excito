#!/usr/bin/env python3
"""Pre-scale a seed accelerogram so its response spectrum sits below the target.

Applies a frequency-dependent scale factor in the Fourier domain to pull down
frequencies where the seed overshoots the target, then writes a new .acc file.
"""

import numpy as np
import sys
import os


def parse_acc(filepath):
    with open(filepath) as f:
        lines = f.readlines()
    header = lines[0].rstrip()
    parts = lines[1].split()
    npts = int(parts[0])
    dt = float(parts[1])
    nadded = int(parts[2])
    acc = []
    for line in lines[2:]:
        for val in line.split():
            acc.append(float(val))
    return header, npts, dt, nadded, np.array(acc[:npts])


def write_acc(filepath, header, npts, dt, nadded, acc):
    with open(filepath, 'w') as f:
        f.write(f"{header}\n")
        f.write(f"{npts} {dt:.4f} {nadded}\n")
        for i, a in enumerate(acc):
            f.write(f"  {a:15.8E}")
            if (i + 1) % 5 == 0:
                f.write("\n")
        if npts % 5 != 0:
            f.write("\n")


def parse_target(filepath):
    with open(filepath) as f:
        lines = f.readlines()
    parts = lines[1].split()
    nfreq = int(parts[0])
    ndamp = int(parts[1])
    freq, sa = [], []
    for i in range(3, 3 + nfreq):
        parts = lines[i].split()
        freq.append(float(parts[0]))
        sa.append(float(parts[3]))  # first damping column
    return np.array(freq), np.array(sa)


def sdof_response_spectrum(acc, dt, freqs, damping=0.05):
    """Compute pseudo-acceleration response spectrum via Newmark-beta."""
    sa = np.zeros(len(freqs))
    for i, f in enumerate(freqs):
        omega = 2 * np.pi * f
        c = 2 * damping * omega
        k = omega ** 2
        # Newmark average acceleration
        u, v = 0.0, 0.0
        max_sa = 0.0
        dt2 = dt * dt
        for ag in acc:
            # Average acceleration method
            denom = 1.0 + 0.5 * c * dt + 0.25 * k * dt2
            du = (-ag - c * v - k * u + 0.5 * dt * (-ag) * 0) / denom
            # Simplified: use exact Duhamel for speed
            pass
        # Use simplified spectral estimate via FFT instead
        pass

    # FFT-based approximate spectrum (much faster)
    n = len(acc)
    nfft = 2 ** int(np.ceil(np.log2(n)))
    acc_fft = np.fft.rfft(acc, n=nfft)
    fft_freqs = np.fft.rfftfreq(nfft, dt)

    for i, f in enumerate(freqs):
        omega = 2 * np.pi * f
        # Transfer function of SDOF oscillator
        H = np.zeros(len(fft_freqs), dtype=complex)
        for j, ff in enumerate(fft_freqs):
            w = 2 * np.pi * ff
            denom = (omega**2 - w**2) + 2j * damping * omega * w
            if abs(denom) > 1e-30:
                H[j] = omega**2 / denom
        resp_fft = acc_fft * H
        resp = np.fft.irfft(resp_fft, n=nfft)[:n]
        sa[i] = np.max(np.abs(resp))

    return sa


def main():
    input_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input')

    acc_file = os.path.join(input_dir, 'elcentro.acc')
    tgt_file = os.path.join(input_dir, 'target.tgt')
    out_file = os.path.join(input_dir, 'elcentro_prescaled.acc')

    print("Reading input files...")
    header, npts, dt, nadded, acc = parse_acc(acc_file)
    tgt_freq, tgt_sa = parse_target(tgt_file)

    print(f"Accelerogram: {npts} pts, dt={dt}s")
    print(f"Target: {len(tgt_freq)} frequencies, {tgt_freq[0]:.2f}-{tgt_freq[-1]:.2f} Hz")

    # Compute current response spectrum at target frequencies
    print("Computing seed response spectrum (this takes a moment)...")
    seed_sa = sdof_response_spectrum(acc, dt, tgt_freq, damping=0.05)

    # Compute frequency-dependent scale factors
    # Where seed > target, scale down. Where seed < target, leave alone (RSPMatch will boost).
    # Use 0.8 * target as the goal so RSPMatch has room to work upward
    scale_target = 0.8 * tgt_sa
    ratios = np.where(seed_sa > scale_target, scale_target / seed_sa, 1.0)

    print("\nPre-scaling ratios:")
    for f, r, s, t in zip(tgt_freq, ratios, seed_sa, tgt_sa):
        status = "SCALE DOWN" if r < 1.0 else "ok"
        print(f"  {f:8.3f} Hz: seed={s:.4f}g target={t:.4f}g ratio={r:.3f} {status}")

    # Apply scaling in Fourier domain
    # Interpolate ratios to full FFT frequency grid
    n = len(acc)
    nfft = 2 ** int(np.ceil(np.log2(n)))
    acc_fft = np.fft.rfft(acc, n=nfft)
    fft_freqs = np.fft.rfftfreq(nfft, dt)

    # Interpolate scale factors across full frequency range
    # Below min target freq: no scaling. Above max: use last ratio.
    scale_curve = np.interp(fft_freqs, tgt_freq, ratios,
                            left=1.0, right=ratios[-1])

    # Smooth the scale curve to avoid ringing
    from scipy.ndimage import gaussian_filter1d
    scale_curve = gaussian_filter1d(scale_curve, sigma=5)
    # Ensure no scaling above 1.0 (only reduce, never boost in pre-processing)
    scale_curve = np.minimum(scale_curve, 1.0)

    # Apply
    acc_fft_scaled = acc_fft * scale_curve
    acc_scaled = np.fft.irfft(acc_fft_scaled, n=nfft)[:n]

    # Write output
    write_acc(out_file, f"Pre-scaled {header}", npts, dt, nadded, acc_scaled)
    print(f"\nWritten: {out_file}")
    print(f"PGA original: {np.max(np.abs(acc)):.4f}g")
    print(f"PGA pre-scaled: {np.max(np.abs(acc_scaled)):.4f}g")


if __name__ == '__main__':
    main()
