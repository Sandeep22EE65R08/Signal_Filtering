import numpy as np
import scipy.signal as signal
from scipy.signal.windows import hamming
import matplotlib.pyplot as plt
from Filter import resample

class DroneSignalProcessor:
    def __init__(self, debug=True):
        self.debug = debug

    @staticmethod
    def fshift(y, offset, Fs):
        """Shift the frequency of the signal."""
        print(f"{len(y)}, offset={offset}, Fs={Fs}")
        x = np.linspace(0.0, len(y) / Fs, len(y))
        return y * np.exp(x * 2j * np.pi * offset)

    @staticmethod
    def consecutive(data, stepsize=1):
        """Group consecutive elements based on a step size."""
        return np.split(data, np.where(np.diff(data) != stepsize)[0] + 1)

    def estimate_offset(self, y, Fs, packet_type="droneid"):
        """Estimate the frequency offset in the signal."""
        nfft_welch = 2048  # Welch's method for calculating the PSD

        if len(y) < nfft_welch:
            return None, False

        window = hamming(len(y))
        y = y * window

        # Calculate power density
        f, Pxx_den = signal.welch(y, Fs, nfft=nfft_welch, return_onesided=False)
        Pxx_den = np.fft.fftshift(Pxx_den)
        f = np.fft.fftshift(f)

        if self.debug:
            plt.semilogy(f, Pxx_den)
            plt.xlabel('Frequency [Hz]')
            plt.ylabel('PSD [V**2/Hz]')
            plt.plot(f, [1.1 * Pxx_den.mean(), ] * len(f))
            plt.show()

        # Add a fake DC carrier to distinguish signal components
        Pxx_den[nfft_welch // 2 - 10:nfft_welch // 2 + 10] = 1.1 * Pxx_den.mean()

        # Identify candidate frequency bands
        candidate_bands = self.consecutive(np.where(Pxx_den > 1.1 * Pxx_den.mean())[0])

        band_found = False
        offset = 0.0

        for band in candidate_bands:
            start = band[0] - nfft_welch / 2
            end = band[-1] - nfft_welch / 2
            bw = (end - start) * (Fs / nfft_welch)
            fend = start * Fs / nfft_welch
            fstart = end * Fs / nfft_welch

            if self.debug:
                print(f"Candidate band fstart: {fstart:.2f}, fend: {fend:.2f}, bw: {bw / 1e6:.2f} MHz")

            # Match candidate bands based on packet type
            if packet_type == "droneid" and (8e6 < bw < 11e6):
                offset = fstart - 0.5 * bw
                band_found = True
                break
            elif packet_type == "c2" and (1.2e6 < bw < 1.95e6):
                offset = fstart - 0.5 * bw
                band_found = True
                break
            elif packet_type == "video" and (18e6 < bw < 22e6):
                offset = fstart - 0.5 * bw
                band_found = True
                break

        if self.debug:
            print(f"Offset found: {offset / 1000:.2f} kHz")
        return offset, band_found

    def process_file(self, file_path, sampling_rate, resample_rate, packet_type="droneid"):
        """Process a signal file for offset estimation and resampling."""
        with open(file_path, "rb") as f:
            samples = np.fromfile(f, dtype=np.complex64)

        offset, band_found = self.estimate_offset(samples, sampling_rate, packet_type)

        if not band_found:
            print("No suitable band found.")
            return

        # Frequency shift to baseband
        packet_data = self.fshift(samples, -1.0 * offset, sampling_rate)

        if self.debug:
            plt.specgram(packet_data, Fs=sampling_rate)
            plt.title("Baseband Spectrogram")
            plt.show()

        # Resample the signal
        if sampling_rate > resample_rate + 0.1e6:
            if self.debug:
                print(f"Resampling from {sampling_rate / 1e6:.2f} MHz to {resample_rate / 1e6:.2f} MHz")
            packet_data = resample(packet_data, sampling_rate, resample_rate)


        if self.debug:
            plt.specgram(packet_data, Fs=resample_rate)
            plt.title("Resampled Spectrogram")
            plt.show()

        return packet_data

# Example Usage
if __name__ == "__main__":
    file_path = '/home/sandeep_bbbs/BBBS/GitHub_collabration_workspace/Drone_detection_optimized_code/netra_50msps.dat'
    sampling_rate = 50e6
    resample_rate = 11e6

    processor = DroneSignalProcessor(debug=True)
    processor.process_file(file_path, sampling_rate, resample_rate, packet_type="droneid")
