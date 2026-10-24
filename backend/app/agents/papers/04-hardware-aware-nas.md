# Hardware-aware search

Latency depends on the device, not only on FLOPs. Depthwise convolutions have few FLOPs but can be memory-bound on GPUs; attention layers are expensive at high resolution because cost grows with the square of the number of tokens. Measure latency on the target device with a warm-up and batch size one, and report the median.

For mobile and microcontroller targets, quantisation to 8-bit integers and operator fusion often matter more than removing a few layers. Energy per inference is roughly latency multiplied by average power.

Down-sample early to keep feature maps small before using attention blocks.
