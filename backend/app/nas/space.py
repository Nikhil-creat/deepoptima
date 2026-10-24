"""Default search space as plain data (no torch import) so the lightweight API image can use it."""
DEFAULT_SPACE = {
    "min_blocks": 3, "max_blocks": 10, "channels": [16, 24, 32, 48, 64, 96, 128],
    "kernels": [3, 5, 7], "blocks": ["conv", "res", "mbconv"],  # add "vit" for hybrid
    "acts": ["relu", "gelu", "silu", "leaky"], "lr": [1e-4, 3e-2], "dropout": [0.0, 0.4], "max_stride_blocks": 3,
}
