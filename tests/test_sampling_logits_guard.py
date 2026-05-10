import pytest
import torch

from MiniCPMO45.utils import InvalidSamplingProbabilitiesError, _validate_sampling_probs


def test_validate_sampling_probs_accepts_valid_probs():
    probs = torch.tensor([[0.2, 0.3, 0.5]], dtype=torch.float32)

    _validate_sampling_probs(probs, context="test")


def test_validate_sampling_probs_rejects_nan():
    probs = torch.tensor([[0.0, float("nan")]], dtype=torch.float32)

    with pytest.raises(InvalidSamplingProbabilitiesError):
        _validate_sampling_probs(probs, context="test")


def test_validate_sampling_probs_rejects_inf():
    probs = torch.tensor([[0.0, float("inf")]], dtype=torch.float32)

    with pytest.raises(InvalidSamplingProbabilitiesError):
        _validate_sampling_probs(probs, context="test")


def test_validate_sampling_probs_rejects_negative_value():
    probs = torch.tensor([[0.5, -0.1, 0.6]], dtype=torch.float32)

    with pytest.raises(InvalidSamplingProbabilitiesError):
        _validate_sampling_probs(probs, context="test")
