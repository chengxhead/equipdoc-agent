from __future__ import annotations

import torch
import torch.nn as nn


class LightCNN(nn.Module):
    """Legacy 1D CNN architecture used by the original bearing experiment."""

    def __init__(self, num_classes: int = 4) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=15, stride=2, padding=7),
            nn.BatchNorm1d(16),
            nn.ReLU(),
            nn.MaxPool1d(2),
            nn.Conv1d(16, 32, kernel_size=7, stride=2, padding=3),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
        )
        self.fc = nn.Linear(32, num_classes)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        features = self.net(inputs.unsqueeze(1)).flatten(1)
        return self.fc(features)

