"""Genotype representation + phenotype (PyTorch) builder for CNN / ViT / hybrid blocks."""
from __future__ import annotations
import copy, random
from dataclasses import dataclass, field, asdict
import torch
import torch.nn as nn

ACTS = {"relu": nn.ReLU, "gelu": nn.GELU, "silu": nn.SiLU, "leaky": lambda: nn.LeakyReLU(0.1)}
BLOCK_TYPES = ["conv", "res", "mbconv", "vit"]


@dataclass
class BlockGene:
    type: str = "conv"
    channels: int = 32
    kernel: int = 3
    stride: int = 1
    act: str = "relu"
    skip: bool = False
    expand: int = 4          # mbconv expansion / vit mlp ratio
    heads: int = 4           # vit only


@dataclass
class Genotype:
    blocks: list[BlockGene] = field(default_factory=list)
    lr: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 128
    optimizer: str = "adamw"
    dropout: float = 0.1
    ops: list[str] = field(default_factory=list)   # mutation operators that produced this candidate

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Genotype":
        g = Genotype(**{k: v for k, v in d.items() if k != "blocks"})
        g.blocks = [BlockGene(**b) for b in d["blocks"]]
        return g

    def clone(self) -> "Genotype":
        return copy.deepcopy(self)


# ---------------- phenotype ----------------
def _act(name: str) -> nn.Module:
    a = ACTS[name]
    return a() if callable(a) else a


class ConvBlock(nn.Module):
    def __init__(self, cin, g: BlockGene):
        super().__init__()
        self.body = nn.Sequential(nn.Conv2d(cin, g.channels, g.kernel, g.stride, g.kernel // 2, bias=False),
                                  nn.BatchNorm2d(g.channels), _act(g.act))
        self.skip = g.skip and cin == g.channels and g.stride == 1

    def forward(self, x):
        y = self.body(x)
        return x + y if self.skip else y


class ResBlock(nn.Module):
    def __init__(self, cin, g: BlockGene):
        super().__init__()
        self.c1 = nn.Sequential(nn.Conv2d(cin, g.channels, g.kernel, g.stride, g.kernel // 2, bias=False),
                                nn.BatchNorm2d(g.channels), _act(g.act))
        self.c2 = nn.Sequential(nn.Conv2d(g.channels, g.channels, g.kernel, 1, g.kernel // 2, bias=False),
                                nn.BatchNorm2d(g.channels))
        self.proj = nn.Identity() if (cin == g.channels and g.stride == 1) else \
            nn.Sequential(nn.Conv2d(cin, g.channels, 1, g.stride, bias=False), nn.BatchNorm2d(g.channels))
        self.act = _act(g.act)

    def forward(self, x):
        return self.act(self.c2(self.c1(x)) + self.proj(x))


class MBConv(nn.Module):
    def __init__(self, cin, g: BlockGene):
        super().__init__()
        mid = cin * g.expand
        self.body = nn.Sequential(
            nn.Conv2d(cin, mid, 1, bias=False), nn.BatchNorm2d(mid), _act(g.act),
            nn.Conv2d(mid, mid, g.kernel, g.stride, g.kernel // 2, groups=mid, bias=False), nn.BatchNorm2d(mid), _act(g.act),
            nn.Conv2d(mid, g.channels, 1, bias=False), nn.BatchNorm2d(g.channels))
        self.skip = g.skip and cin == g.channels and g.stride == 1

    def forward(self, x):
        y = self.body(x)
        return x + y if self.skip else y


class ViTBlock(nn.Module):
    """Operates on feature maps: flatten -> transformer encoder layer -> reshape."""
    def __init__(self, cin, g: BlockGene):
        super().__init__()
        self.proj = nn.Conv2d(cin, g.channels, 1) if cin != g.channels else nn.Identity()
        heads = g.heads if g.channels % g.heads == 0 else 1
        self.enc = nn.TransformerEncoderLayer(g.channels, heads, g.channels * g.expand, batch_first=True,
                                              activation="gelu", norm_first=True)
        self.down = nn.AvgPool2d(g.stride) if g.stride > 1 else nn.Identity()

    def forward(self, x):
        x = self.down(self.proj(x))
        b, c, h, w = x.shape
        t = self.enc(x.flatten(2).transpose(1, 2))
        return t.transpose(1, 2).reshape(b, c, h, w)


BUILDERS = {"conv": ConvBlock, "res": ResBlock, "mbconv": MBConv, "vit": ViTBlock}


class Phenotype(nn.Module):
    def __init__(self, g: Genotype, in_ch=3, num_classes=10):
        super().__init__()
        layers, c = [], in_ch
        first = g.blocks[0].channels if g.blocks else 32
        layers.append(nn.Sequential(nn.Conv2d(in_ch, first, 3, 1, 1, bias=False), nn.BatchNorm2d(first), nn.ReLU()))
        c = first
        for b in g.blocks:
            layers.append(BUILDERS[b.type](c, b))
            c = b.channels
        self.features = nn.Sequential(*layers)
        self.head = nn.Sequential(nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(g.dropout), nn.Linear(c, num_classes))

    def forward(self, x):
        return self.head(self.features(x))


def build_model(g: Genotype, in_ch=3, num_classes=10) -> nn.Module:
    return Phenotype(g, in_ch, num_classes)


def count_params(m: nn.Module) -> int:
    return sum(p.numel() for p in m.parameters() if p.requires_grad)


# ---------------- search space sampling ----------------
from app.nas.space import DEFAULT_SPACE  # noqa: E402  (plain data; re-exported for existing imports)


def random_block(space: dict, stride=1) -> BlockGene:
    t = random.choice(space["blocks"])
    return BlockGene(type=t, channels=random.choice(space["channels"]),
                     kernel=3 if t == "vit" else random.choice(space["kernels"]),
                     stride=stride, act=random.choice(space["acts"]), skip=random.random() < 0.5,
                     expand=random.choice([2, 4]), heads=random.choice([2, 4]))


def random_genotype(space: dict = DEFAULT_SPACE) -> Genotype:
    n = random.randint(space["min_blocks"], space["max_blocks"])
    strides = set(random.sample(range(n), min(space["max_stride_blocks"], n)))
    g = Genotype(blocks=[random_block(space, 2 if i in strides else 1) for i in range(n)])
    g.lr = 10 ** random.uniform(__import__("math").log10(space["lr"][0]), __import__("math").log10(space["lr"][1]))
    g.dropout = random.uniform(*space["dropout"])
    return g
