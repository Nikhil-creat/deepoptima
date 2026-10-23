"""Zero-cost proxies + successive halving so most candidates never need a full training run."""
import math, torch, torch.nn as nn
from app.nas.genotype import Genotype, build_model, count_params

@torch.no_grad()
def naswot_score(g: Genotype, batch: int = 32, res: int = 32) -> float:
    """NASWOT-lite: log-determinant of the ReLU-activation kernel on a random batch (higher = more expressive)."""
    model = build_model(g).eval(); codes: list[torch.Tensor] = []
    def hook(_, __, out): codes.append((out.flatten(1) > 0).float())
    hs = [m.register_forward_hook(hook) for m in model.modules() if isinstance(m, (nn.ReLU, nn.GELU, nn.SiLU, nn.LeakyReLU))]
    model(torch.randn(batch, 3, res, res))
    for h in hs: h.remove()
    if not codes: return 0.0
    c = torch.cat(codes, 1); K = c @ c.T + (1 - c) @ (1 - c).T
    sign, logdet = torch.linalg.slogdet(K + 1e-3 * torch.eye(batch))
    return float(logdet) if sign > 0 else -1e9

def proxy_filter(genotypes: list[Genotype], keep_frac: float = 0.5, max_params: int = 5_000_000) -> list[Genotype]:
    scored = []
    for g in genotypes:
        try:
            if count_params(build_model(g)) > max_params: continue
            scored.append((naswot_score(g), g))
        except Exception:
            continue
    scored.sort(key=lambda s: -s[0])
    return [g for _, g in scored[: max(1, int(len(scored) * keep_frac))]]

def successive_halving(results: list[dict], eta: int = 3) -> list[dict]:
    """Keep the top 1/eta by current accuracy (then grow budget); use between rungs of epochs."""
    return sorted(results, key=lambda r: -r["accuracy"])[: max(1, len(results) // eta)]

def carbon_estimate_g(gpu_watts: float, seconds: float, grid_g_per_kwh: float = 700) -> float:
    """Rough CO2e grams for a trial (India grid ~700 g/kWh; override per region)."""
    return gpu_watts * seconds / 3.6e6 * grid_g_per_kwh
