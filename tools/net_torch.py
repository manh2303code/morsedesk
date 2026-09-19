"""Định nghĩa mạng PyTorch. Chỉ dùng lúc huấn luyện và xuất ONNX; runtime không cần torch."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from morsedesk.constants import FEAT_DIM
from morsedesk.model.vocab import VOCAB

CONFIG_DEFAULT = {"feat_dim": FEAT_DIM, "n_classes": len(VOCAB), "hidden": 96}


def output_length(t: int) -> int:
    """Conv1d k=5, pad=2, stride=2 ở tầng hai: L_out = (L-1)//2 + 1."""
    return (t - 1) // 2 + 1


class MorseNet(nn.Module):
    def __init__(self, feat_dim: int = FEAT_DIM, n_classes: int = len(VOCAB), hidden: int = 96) -> None:
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(feat_dim, 32, 5, padding=2), nn.ReLU(),
            nn.Conv1d(32, 64, 5, stride=2, padding=2), nn.ReLU(),
            nn.Conv1d(64, 64, 5, padding=2), nn.ReLU(),
        )
        self.gru = nn.GRU(64, hidden, batch_first=True, bidirectional=True)
        self.fc = nn.Linear(2 * hidden, n_classes)

    def forward(self, feats: torch.Tensor) -> torch.Tensor:  # [B, T, F] -> [B, T', C]
        x = self.conv(feats.transpose(1, 2)).transpose(1, 2)
        x, _ = self.gru(x)
        return F.log_softmax(self.fc(x), dim=-1)


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
