#!/usr/bin/env python3
"""Plot RSPMatch results — target vs matched vs original spectra, plus time histories."""

import sys
import os
import re
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

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

    # Line 1: header
    # Line 2: npts, dt, nadded
    parts = lines[1].split()
    npts = int(parts[0])
    dt = float(parts[1])

    # Remaining lines: acceleration values (free format, may be multiple per line)
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

def main():
    if len(sys.argv) < 2:
        # Try to find the most recent run directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(script_dir, 'output')
        if not os.path.isdir(output_dir):
            print("Usage: python3 plot_results.py <run-directory>")
            print("   eg: python3 plot_results.py output/run-03_27_26_1552")
            sys.exit(1)
        runs = sorted([d for d in os.listdir(output_dir) if d.startswith('run-')])
        if not runs:
            print("No run directories found in output/")
            sys.exit(1)
        run_dir = os.path.join(output_dir, runs[-1])
        print(f"Using most recent run: {run_dir}")
    else:
        run_dir = sys.argv[1]

    matched_rsp = os.path.join(run_dir, 'matched.rsp')
    matched_acc = os.path.join(run_dir, 'matched.acc')
    original_acc = os.path.join(run_dir, 'elcentro.acc')

    if not os.path.exists(matched_rsp):
        print(f"Error: {matched_rsp} not found")
        sys.exit(1)

    # Parse spectrum data
    freq, target, computed, initial = parse_rsp(matched_rsp)

    # Create figure
    has_acc = os.path.exists(matched_acc) and os.path.exists(original_acc)
    if has_acc:
        fig, axes = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 2]})
        ax1 = axes[0]
        ax2 = axes[1]
    else:
        fig, ax1 = plt.subplots(1, 1, figsize=(12, 6))

    # --- Plot 1: Response Spectra ---
    ax1.loglog(freq, target, 'k-', linewidth=2.5, label='Target (Design Spectrum)', zorder=3)
    ax1.loglog(freq, computed, 'r-o', linewidth=1.5, markersize=5, label='Matched', zorder=2)
    ax1.loglog(freq, initial, 'b--', linewidth=1, alpha=0.6, label='Original (Scaled El Centro)', zorder=1)

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

    # Add misfit annotation
    misfit = np.abs((computed - target) / target) * 100
    avg_misfit = np.mean(misfit)
    ax1.annotate(f'Avg misfit: {avg_misfit:.1f}%',
                xy=(0.02, 0.02), xycoords='axes fraction',
                fontsize=10, color='gray',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.8))

    # --- Plot 2: Time Histories ---
    if has_acc:
        time_orig, acc_orig = parse_acc(original_acc)
        time_match, acc_match = parse_acc(matched_acc)

        ax2.plot(time_orig, acc_orig, 'b-', linewidth=0.5, alpha=0.5, label='Original (El Centro)')
        ax2.plot(time_match, acc_match, 'r-', linewidth=0.5, alpha=0.7, label='Matched')

        ax2.set_xlabel('Time (seconds)')
        ax2.set_ylabel('Acceleration (g)')
        ax2.set_title('Time History Comparison', fontsize=14, fontweight='bold')
        ax2.legend(loc='upper right', fontsize=10)
        ax2.grid(True, alpha=0.3)

        # Add PGA annotations
        pga_orig = np.max(np.abs(acc_orig))
        pga_match = np.max(np.abs(acc_match))
        ax2.annotate(f'PGA original: {pga_orig:.3f}g | PGA matched: {pga_match:.3f}g',
                    xy=(0.02, 0.02), xycoords='axes fraction',
                    fontsize=10, color='gray',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.8))

    plt.tight_layout()

    # Save
    plot_path = os.path.join(run_dir, 'results.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"Saved: {plot_path}")

    # Also try to show it
    try:
        plt.show()
    except:
        pass

if __name__ == '__main__':
    main()
