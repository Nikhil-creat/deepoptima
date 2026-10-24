# Zero-cost proxies and successive halving

Training every candidate fully is wasteful. Zero-cost proxies score an untrained network in one forward pass. A common one measures how distinct the activation patterns are for different inputs on a random batch: networks that separate inputs well at initialisation tend to train better. Parameter and FLOP limits remove oversized candidates before any GPU time is spent.

Successive halving trains many candidates for a very short budget, keeps the best fraction, and gives the survivors a larger budget, repeating until a few remain. Combine both: proxy filter first, then halving.

Proxies are noisy; use them to discard the worst half, not to pick the winner.
