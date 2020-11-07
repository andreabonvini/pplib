from copy import deepcopy
from dataclasses import dataclass
from typing import List

import numpy as np

from pp.core.model import PointProcessModel


@dataclass()
class Pole:
    """
    Pole or pair of conjugate poles,
    """

    # TODO add Documentation
    pos: complex  # position on the complex plane
    frequency: float  # pragma: no cover
    power: float  # pragma: no cover
    residual: float  # pragma: no cover


@dataclass
class SpectralAnalysis:
    frequencies: np.array  # Hz
    powers: np.array  # ms^2 / Hz
    poles: List[Pole]
    comps: List[List[complex]]


class SpectralAnalyzer:
    def __init__(self, model: PointProcessModel, aggregate: bool = True):
        """
        Args:
            model: Trained PointProcessModel, we'll use the AR parameters learnt by this model in order to conduct
            the spectral analysis.
            aggregate: if True, poles' powers will be aggregated with
            their corresponding complex conjugate
        """
        self.model = model
        self.aggregate = aggregate

    def hrv_indices(self):
        pass

    def psd(self) -> SpectralAnalysis:
        """
        Compute Power Spectral Density for the given model.
        """
        return self._compute_psd(self.model.theta, self.model.wn, self.model.k)

    def _compute_psd(
        self, theta: np.ndarray, wn: np.ndarray, k: float
    ) -> SpectralAnalysis:  # pragma: no cover
        thetap = deepcopy(theta[1:]) if self.model.hasTheta0 else deepcopy(theta[:])
        mean_interval = np.mean(wn)
        var = mean_interval ** 3 / k
        var = 1e6 * var  # from [s^2] to [ms^2]
        fsamp = 1 / mean_interval
        ar = np.r_[1, -thetap]  # [1, -θ1, -θ2, ..., θp]
        # Compute poles' complex values
        poles_values = np.roots(ar)
        # Order them by absolute angle
        poles_values = sorted(poles_values, key=lambda x: abs(np.angle(x)))

        # Fix AR models that might have become slightly unstable due to the estimation process
        # using an exponential decay (see Stoica and Moses, Signal Processing 26(1) 1992)
        mod_scale = min(0.99 / max(np.abs(poles_values)), 1)
        poles_values = mod_scale * poles_values
        thetap = thetap * np.cumprod(np.ones(thetap.shape) * mod_scale)

        fs = np.linspace(-0.5, 0.5, 2048)
        # z = e^(-2πfT)
        # z: unit delay operator
        z = np.exp(2j * np.pi * fs)
        # P(z) = (σ^2*T)/ |1+θ1*z^(-1)+...+θp*z^(-p)|^2
        # σ^2 : Sample variance
        # T: sampling interval
        powers = (var / fsamp) / abs(np.polyval(np.r_[1, -thetap], np.conj(z))) ** 2
        frequencies = fs * fsamp
        poles_residuals = [
            1
            / (
                p
                * np.prod(p - [val for val in poles_values if val is not p])
                * np.prod(1 / p - np.conj(poles_values))
            )
            for p in poles_values
        ]

        poles_frequencies = [np.angle(p) / (2 * np.pi) * fsamp for p in poles_values]
        poles_powers = [var * np.real(p) for p in poles_residuals]
        # We also save the spectral components for each frequency value for each pole
        poles_comps = []
        ref_poles = 1 / np.conj(poles_values)
        for i in range(len(poles_values)):
            pp = poles_residuals[i] * poles_values[i] / (z - poles_values[i])
            refpp = -np.conj(poles_residuals[i]) * ref_poles[i] / (z - ref_poles[i])
            poles_comps.append(var / fsamp * (pp + refpp))

        poles_comps_agg = [deepcopy(poles_comps[0])]

        # Aggregate complex conjugate poles in poles_comps_agg

        for i in range(1, len(poles_values)):
            if np.isclose(poles_values[i], np.conj(poles_values[i - 1])):
                poles_comps_agg[-1] += poles_comps[i]
            else:
                poles_comps_agg.append(deepcopy(poles_comps[i]))

        poles = [
            Pole(pos, freq, power, res)
            for pos, freq, power, res in zip(
                poles_values, poles_frequencies, poles_powers, poles_residuals,
            )
        ]

        return SpectralAnalysis(
            frequencies,
            powers,
            poles,
            poles_comps_agg if self.aggregate else poles_comps,
        )
