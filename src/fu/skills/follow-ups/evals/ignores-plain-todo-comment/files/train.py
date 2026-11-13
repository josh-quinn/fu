import torch
import torch.nn as nn


def loss_fn(logits, targets):
    return nn.functional.cross_entropy(logits, targets)


def train(model, loader, opt):
    for x, y in loader:
        opt.zero_grad()
        loss = loss_fn(model(x), y)
        loss.backward()
        opt.step()
