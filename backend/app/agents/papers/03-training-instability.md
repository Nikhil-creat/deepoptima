# Diagnosing diverging or stalled trials

Loss becomes NaN or infinite: lower the learning rate by about ten times, add gradient-norm clipping (a clip value around 1 to 5 is typical), and check for very deep stacks without skip connections.

Loss plateaus near the chance level: the learning rate is often too small, or normalisation layers are missing. Add batch normalisation and try a warm-up of the learning rate for the first epoch.

Large train/test gap: increase dropout, weight decay or augmentation, or reduce width.

SGD with a high learning rate diverges more often than AdamW on short schedules; prefer AdamW for short-epoch evaluation.
