#!/usr/bin/env python3
"""Plot RSPMatch results — target vs matched vs original spectra, plus time histories."""

import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib

matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.size'] = 11


def parse_rsp(filepath):
    """Parse an RSPMatch .rsp file and return freq, target, computed, initial arrays."""
    freq, target, computed, initial = [], [], [], []
    in_table = False
    with open(filepath) as f:
        for line in f:
            if 'Freq' in line and 'Damping' in line and 'Target' in line:
                in_table = True
                continue
            if in_table:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        fr = float(parts[0])
                        if fr > 0:
                            freq.append(fr)
                            target.append(float(parts[2]))
                            computed.append(float(parts[3]))
                            initial.append(float(parts[4]))
                    except ValueError:
                        continue
    return np.array(freq), np.array(target), np.array(computed), np.array(initial)


def parse_acc(filepath):
    """Parse an RSPMatch .acc file and return time and acceleration arrays."""
    with open(filepath) as f:
        lines = f.readlines()
    parts = lines[1].split()
    npts = int(parts[0])
    dt = float(parts[1])
    acc = []
    for line in lines[2:]:
        for val in line.split():
            try:
                acc.append(float(val))
            except ValueError:
                continue
    acc = np.array(acc[:npts])
    time = np.arange(len(acc)) * dt
    return time, acc


def compute_response_spectrum(acc, dt, freqs, damping=0.05):
    """Compute pseudo-acceleration response spectrum via FFT transfer function."""
    n = len(acc)
    nfft = 2 ** int(np.ceil(np.log2(n)))
    acc_fft = np.fft.rfft(acc, n=nfft)
    fft_freqs = np.fft.rfftfreq(nfft, dt)
    sa = np.zeros(len(freqs))
    for i, f in enumerate(freqs):
        omega = 2 * np.pi * f
        H = np.zeros(len(fft_freqs), dtype=complex)
        for j, ff in enumerate(fft_freqs):
            w = 2 * np.pi * ff
            denom = (omega**2 - w**2) + 2j * damping * omega * w
            if abs(denom) > 1e-30:
                H[j] = omega**2 / denom
        resp = np.fft.irfft(acc_fft * H, n=nfft)[:n]
        sa[i] = np.max(np.abs(resp))
    return sa


def find_acc_file(run_dir, names):
    """Find the first existing file from a list of candidate names."""
    for name in names:
        path = os.path.join(run_dir, name)
        if os.path.exists(path):
            return path
    return None


def main():
    if len(sys.argv) < 2:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, 'output')
        if not os.path.isdir(output_dir):
            print("Usage: python3 plot_results.py <run-directory>")
            sys.exit(1)
        runs = sorted([d for d in os.listdir(output_dir) if d.startswith(('run-', 'multipass-'))])
        if not runs:
            print("No run directories found in output/")
            sys.exit(1)
        run_dir = os.path.join(output_dir, runs[-1])
        print(f"Using most recent run: {run_dir}")
    else:
        run_dir = sys.argv[1]

    matched_rsp = os.path.join(run_dir, 'matched.rsp')
    if not os.path.exists(matched_rsp):
        print(f"Error: {matched_rsp} not found")
        sys.exit(1)

    # Parse spectrum data from .rsp file
    freq, target, computed, initial_from_rsp = parse_rsp(matched_rsp)

    # Find accelerogram files
    matched_acc_path = find_acc_file(run_dir, ['matched.acc'])
    # Search for original accelerogram - check all common names and any .acc that isn't matched
    original_candidates = ['elcentro.acc', 'holtville.acc', 'treasure_island.acc', 'seed.acc', 'input.acc']
    original_acc_path = find_acc_file(run_dir, original_candidates)
    if original_acc_path is None:
        # Fall back: find any .acc file that isn't matched.acc
        for f in os.listdir(run_dir):
            if f.endswith('.acc') and f != 'matched.acc':
                original_acc_path = os.path.join(run_dir, f)
                break

    # If the "initial" column in the .rsp is from a pre-scaled record,
    # compute the true original spectrum from the raw .acc file
    original_sa = initial_from_rsp
    original_label = 'Initial (from .rsp)'
    if original_acc_path:
        print(f"Computing original spectrum from {os.path.basename(original_acc_path)}...")
        _, orig_acc = parse_acc(original_acc_path)
        computed_orig_sa = compute_response_spectrum(orig_acc, 0.02, freq)
        # If the .rsp initial values are very different from the raw file's spectrum,
        # it means a pre-scaled record was used — show the raw one instead
        if len(computed_orig_sa) == len(initial_from_rsp):
            ratio = np.mean(np.abs(computed_orig_sa - initial_from_rsp) / (initial_from_rsp + 1e-10))
            if ratio > 0.3:  # more than 30% different = pre-scaled was used
                original_sa = computed_orig_sa
                original_label = f'Original ({os.path.basename(original_acc_path)})'
                print(f"  Using computed spectrum (pre-scaled seed detected)")
            else:
                original_label = f'Original ({os.path.basename(original_acc_path)})'
                print(f"  Using .rsp initial column (matches raw file)")

    # Create figure
    has_acc = matched_acc_path is not None and original_acc_path is not None
    if has_acc:
        fig, axes = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 2]})
        ax1, ax2 = axes
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(12, 6))

    # --- Plot 1: Response Spectra ---
    # Check for --linear flag
    use_linear = '--linear' in sys.argv

    if use_linear:
        ax1.plot(freq, target, 'k-', linewidth=2.5, label='Target (Design Spectrum)', zorder=3)
        ax1.plot(freq, computed, 'r-o', linewidth=1.5, markersize=5, label='Matched', zorder=2)
        ax1.plot(freq, original_sa, 'b--', linewidth=1.2, alpha=0.7, label=original_label, zorder=1)
        ax1.set_xscale('log')
    else:
        ax1.loglog(freq, target, 'k-', linewidth=2.5, label='Target (Design Spectrum)', zorder=3)
        ax1.loglog(freq, computed, 'r-o', linewidth=1.5, markersize=5, label='Matched', zorder=2)
        ax1.loglog(freq, original_sa, 'b--', linewidth=1.2, alpha=0.7, label=original_label, zorder=1)

    # Shade the well-matched region
    good_mask = np.abs((computed - target) / target) < 0.05
    if np.any(good_mask):
        good_freqs = freq[good_mask]
        ax1.axvspan(good_freqs.min(), good_freqs.max(), alpha=0.08, color='green',
                    label=f'Good match region ({good_freqs.min():.1f}-{good_freqs.max():.1f} Hz)')

    ax1.set_xlabel('Frequency (Hz)')
    ax1.set_ylabel('Spectral Acceleration (g)')
    ax1.set_title('Response Spectrum Comparison', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper right', fontsize=10)
    ax1.grid(True, which='both', alpha=0.3)
    ax1.set_xlim(0.1, 20)

    # Misfit annotation
    misfit = np.abs((computed - target) / target) * 100
    avg_misfit = np.mean(misfit)
    ax1.annotate(f'Avg misfit: {avg_misfit:.1f}%',
                 xy=(0.02, 0.02), xycoords='axes fraction', fontsize=10, color='gray',
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.8))

    # --- Plot 2: Time Histories ---
    if has_acc:
        time_orig, acc_orig = parse_acc(original_acc_path)
        time_match, acc_match = parse_acc(matched_acc_path)

        ax2.plot(time_orig, acc_orig, 'b-', linewidth=0.5, alpha=0.5,
                 label=f'Original ({os.path.basename(original_acc_path)})')
        ax2.plot(time_match, acc_match, 'r-', linewidth=0.5, alpha=0.7, label='Matched')

        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylabel('Acceleration (g)')
        ax2.set_title('Time History Comparison', fontsize=14, fontweight='bold')
        ax2.legend(loc='upper right', fontsize=10)
        ax2.grid(True, alpha=0.3)

        pga_orig = np.max(np.abs(acc_orig))
        pga_match = np.max(np.abs(acc_match))
        ax2.annotate(f'PGA original: {pga_orig:.3f}g | PGA matched: {pga_match:.3f}g',
                     xy=(0.02, 0.02), xycoords='axes fraction', fontsize=10, color='gray',
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.8))

    plt.tight_layout()

    plot_path = os.path.join(run_dir, 'results.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {plot_path}")

    try:
        plt.show()
    except:
        pass


if __name__ == '__main__':
    main()
