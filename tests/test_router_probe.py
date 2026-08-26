"""Smoke test for src.diagnostics.router_probe.

Validates that the probe attaches to a HF MoE-shaped module, records
deterministic top-1 / top-2 expert decisions, and computes flip rate / Jaccard
correctly between two probe runs on identical inputs.
"""

from __future__ import annotations

import torch
from torch import nn

from src.diagnostics.router_probe import RouterProbe


class FakeMoEBlock(nn.Module):
    """Minimal MoE block: a 'gate' linear of (hidden -> num_experts)."""

    def __init__(self, hidden: int = 8, num_experts: int = 4) -> None:
        super().__init__()
        self.block_sparse_moe = nn.Module()
        self.block_sparse_moe.gate = nn.Linear(hidden, num_experts, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block_sparse_moe.gate(x)


class FakeMoEModel(nn.Module):
    """Two stacked MoE layers, named like HF Mixtral."""

    def __init__(self, n_layers: int = 2, hidden: int = 8, num_experts: int = 4) -> None:
        super().__init__()
        self.model = nn.Module()
        self.model.layers = nn.ModuleList(
            [FakeMoEBlock(hidden, num_experts) for _ in range(n_layers)]
        )

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        return [layer(x) for layer in self.model.layers]


def test_probe_attaches_and_records():
    torch.manual_seed(0)
    model = FakeMoEModel(n_layers=2, hidden=8, num_experts=4)
    x = torch.randn(3, 8)  # 3 tokens

    probe = RouterProbe()
    n_hooks = probe.attach(model)
    assert n_hooks == 2  # one gate per layer

    with torch.no_grad():
        model(x)

    probe.detach()
    assert len(probe.records) == 6  # 2 layers x 3 tokens
    summary = probe.summary()
    assert summary["n_gates"] == 2
    assert summary["n_records"] == 6


def test_probe_compare_zero_flip_on_identical():
    """Same model, same input, two probes -> zero flip rate."""
    torch.manual_seed(1)
    model = FakeMoEModel()
    x = torch.randn(5, 8)

    pa = RouterProbe()
    pa.attach(model)
    with torch.no_grad():
        model(x)
    pa.detach()

    pb = RouterProbe()
    pb.attach(model)
    with torch.no_grad():
        model(x)
    pb.detach()

    diff = RouterProbe.compare(pa, pb)
    assert diff["top1_flip_rate_overall"] == 0.0
    assert diff["jaccard_topk_mean"] == 0.0


def test_probe_compare_detects_flip_on_perturbed():
    """Perturb gate weights between runs -> non-zero flip rate."""
    torch.manual_seed(2)
    model = FakeMoEModel()
    x = torch.randn(20, 8)

    pa = RouterProbe()
    pa.attach(model)
    with torch.no_grad():
        model(x)
    pa.detach()

    # Perturb every gate.
    with torch.no_grad():
        for m in model.modules():
            if isinstance(m, nn.Linear):
                m.weight.add_(torch.randn_like(m.weight) * 0.5)

    pb = RouterProbe()
    pb.attach(model)
    with torch.no_grad():
        model(x)
    pb.detach()

    diff = RouterProbe.compare(pa, pb)
    assert 0.0 < diff["top1_flip_rate_overall"] <= 1.0


class FakeSwiGLUExpert(nn.Module):
    """A dense SwiGLU expert with a `gate_proj` that must NOT be matched."""

    def __init__(self, hidden: int = 8, inter: int = 32) -> None:
        super().__init__()
        self.gate_proj = nn.Linear(hidden, inter, bias=False)
        self.up_proj = nn.Linear(hidden, inter, bias=False)
        self.down_proj = nn.Linear(inter, hidden, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.down_proj(self.up_proj(x))


class FakeQwen3MoEBlock(nn.Module):
    """Qwen3-MoE-shaped block: `mlp.gate` router + N experts w/ gate_proj."""

    def __init__(self, hidden: int = 8, num_experts: int = 4, inter: int = 32) -> None:
        super().__init__()
        self.mlp = nn.Module()
        self.mlp.gate = nn.Linear(hidden, num_experts, bias=False)
        self.mlp.experts = nn.ModuleList(
            [FakeSwiGLUExpert(hidden, inter) for _ in range(num_experts)]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.mlp.gate(x)


class FakeQwen3MoEModel(nn.Module):
    def __init__(self, n_layers: int = 2, hidden: int = 8, num_experts: int = 4) -> None:
        super().__init__()
        self.model = nn.Module()
        self.model.layers = nn.ModuleList(
            [FakeQwen3MoEBlock(hidden, num_experts) for _ in range(n_layers)]
        )

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        return [layer(x) for layer in self.model.layers]


def test_probe_ignores_dense_gate_proj():
    """Only the real `mlp.gate` router is hooked, never expert `gate_proj`."""
    model = FakeQwen3MoEModel(n_layers=2, hidden=8, num_experts=4)
    probe = RouterProbe()
    n_hooks = probe.attach(model)
    # 2 layers -> exactly 2 routers, despite 2*4=8 expert gate_proj modules.
    assert n_hooks == 2


def test_out_features_guard_excludes_large_linears():
    """A Linear that matches a name pattern but is FFN-sized is rejected."""
    model = FakeQwen3MoEModel(n_layers=1, hidden=8, num_experts=4)
    probe = RouterProbe(max_gate_out_features=2)  # smaller than num_experts=4
    try:
        probe.attach(model)
        raised = False
    except RuntimeError:
        raised = True
    assert raised  # no gate qualifies under the tighter guard


def test_kl_computed_when_store_probs():
    torch.manual_seed(3)
    model = FakeMoEModel()
    x = torch.randn(10, 8)

    pa = RouterProbe(store_probs=True)
    pa.attach(model)
    with torch.no_grad():
        model(x)
    pa.detach()

    with torch.no_grad():
        for m in model.modules():
            if isinstance(m, nn.Linear):
                m.weight.add_(torch.randn_like(m.weight) * 0.3)

    pb = RouterProbe(store_probs=True)
    pb.attach(model)
    with torch.no_grad():
        model(x)
    pb.detach()

    diff = RouterProbe.compare(pa, pb)
    assert diff["kl_mean"] is not None
    assert diff["n_kl_records"] == 20  # 2 layers x 10 tokens
    assert diff["kl_mean"] >= 0.0
