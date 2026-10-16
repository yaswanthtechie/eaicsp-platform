
"""Shared reproducibility and training utilities."""

import copy
import random
from typing import Callable

import numpy as np
import torch


def set_seed(seed: int = 42) -> None:
    """Set random seeds for reproducible experiments."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def fit_with_early_stopping(
    model,
    train_loader,
    val_loader,
    optimizer,
    loss_fn,
    device,
    epochs: int,
    patience: int,
    forward_batch: Callable,
    on_epoch_end: Callable | None = None,
) -> dict:
    """
    Train a model with validation-based early stopping.

    forward_batch(model, batch, device) must return (prediction, target).
    Gradient clipping is consistently applied with max_norm=1.0.
    """
    if epochs < 1:
        raise ValueError("epochs must be >= 1")
    if patience < 1:
        raise ValueError("patience must be >= 1")

    if len(train_loader) == 0 or len(val_loader) == 0:
        raise RuntimeError("Training or validation dataset is empty.")

    best_val_loss = float("inf")
    best_state = None
    best_epoch = 0
    patience_count = 0
    epochs_completed = 0
    history = []

    for epoch in range(1, epochs + 1):
        model.train()
        train_losses = []

        for batch in train_loader:
            optimizer.zero_grad()

            prediction, target = forward_batch(model, batch, device)
            loss = loss_fn(prediction, target)

            if not torch.isfinite(loss):
                continue

            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                max_norm=1.0,
            )
            optimizer.step()
            train_losses.append(loss.item())

        model.eval()
        val_losses = []

        with torch.no_grad():
            for batch in val_loader:
                prediction, target = forward_batch(model, batch, device)
                val_loss = loss_fn(prediction, target)

                if torch.isfinite(val_loss):
                    val_losses.append(val_loss.item())

        if not train_losses or not val_losses:
            raise RuntimeError(
                "Training or validation produced no finite losses."
            )

        train_loss = float(np.mean(train_losses))
        val_loss = float(np.mean(val_losses))
        epochs_completed = epoch

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
        })

        if on_epoch_end is not None:
            on_epoch_end(epoch, train_loss, val_loss)

        print(
            f"Epoch {epoch:02d}/{epochs} | "
            f"train_loss={train_loss:.5f} | "
            f"val_loss={val_loss:.5f}"
        )

        if np.isfinite(val_loss) and val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = copy.deepcopy(model.state_dict())
            best_epoch = epoch
            patience_count = 0
        else:
            patience_count += 1

        if patience_count >= patience:
            print("Early stopping: validation loss did not improve.")
            break

    if best_state is None:
        raise RuntimeError(
            "No finite validation improvement; model never trained"
        )

    model.load_state_dict(best_state)

    return {
        "best_state": best_state,
        "best_val_loss": float(best_val_loss),
        "best_epoch": int(best_epoch),
        "epochs_completed": int(epochs_completed),
        "history": history,
    }
