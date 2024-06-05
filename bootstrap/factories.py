#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright © 2024 Théo Morales <theo.morales.fr@gmail.com>
#
# Distributed under terms of the MIT license.

"""
All factories.
"""

import os
from dataclasses import asdict
from typing import Any, Optional, Tuple

import hydra_zen
import torch
import wandb
import yaml
from hydra.core.hydra_config import HydraConfig
from hydra_zen import just
from hydra_zen.typing import Partial
from rich.console import Console, Group
from rich.panel import Panel
from rich.pretty import Pretty
from rich.syntax import Syntax
from torch.utils.data import DataLoader, Dataset

from conf import project as project_conf
from model import TransparentDataParallel
from src.base_tester import BaseTester
from src.base_trainer import BaseTrainer
from utils import load_model_ckpt, to_cuda_

console = Console()


def make_datasets(
    training_mode: bool, seed: int, dataset_partial: Partial[Dataset[Any]]
) -> Tuple[Optional[Dataset[Any]], Optional[Dataset[Any]], Optional[Dataset[Any]]]:
    train_dataset: Optional[Dataset[Any]] = None
    val_dataset: Optional[Dataset[Any]] = None
    test_dataset: Optional[Dataset[Any]] = None
    with console.status("Loading datasets...", spinner="monkey"):
        if training_mode:
            train_dataset = dataset_partial(split="train", seed=seed)
            val_dataset = dataset_partial(split="val", seed=seed)
        else:
            test_dataset = dataset_partial(split="test", augment=False, seed=seed)
    return train_dataset, val_dataset, test_dataset


def make_dataloaders(
    data_loader_partial: Partial[DataLoader[Dataset[Any]]],
    train_dataset: Optional[Dataset[Any]],
    val_dataset: Optional[Dataset[Any]],
    test_dataset: Optional[Dataset[Any]],
    training_mode: bool,
    seed: int,
) -> Tuple[
    Optional[DataLoader[Dataset[Any]]],
    Optional[DataLoader[Dataset[Any]]],
    Optional[DataLoader[Dataset[Any]]],
]:
    generator = None
    if project_conf.REPRODUCIBLE:
        generator = torch.Generator()
        generator.manual_seed(seed)

    train_loader_inst: Optional[DataLoader[Any]] = None
    val_loader_inst: Optional[DataLoader[Dataset[Any]]] = None
    test_loader_inst: Optional[DataLoader[Any]] = None
    if training_mode:
        if train_dataset is None or val_dataset is None:
            raise ValueError(
                "train_dataset and val_dataset must be defined in training mode!"
            )
        train_loader_inst = data_loader_partial(train_dataset, generator=generator)
        val_loader_inst = data_loader_partial(
            val_dataset, generator=generator, shuffle=False, drop_last=False
        )
    else:
        if test_dataset is None:
            raise ValueError("test_dataset must be defined in testing mode!")
        test_loader_inst = data_loader_partial(
            test_dataset, generator=generator, shuffle=False, drop_last=False
        )
    return train_loader_inst, val_loader_inst, test_loader_inst


def make_model(
    model_partial: Partial[torch.nn.Module], dataset: Partial[Dataset[Any]]
) -> torch.nn.Module:
    with console.status("Loading model...", spinner="runner"):
        model_inst = model_partial(
            encoder_input_dim=just(dataset).img_dim ** 2  # type: ignore
        )  # Use just() to get the config out of the Zen-Partial

    return model_inst


def parallelize_model(model: torch.nn.Module) -> torch.nn.Module:
    console.print(
        f"[*] Number of GPUs: {torch.cuda.device_count()}",
        style="bold cyan",
    )
    if torch.cuda.device_count() > 1:
        console.print(
            f"-> Using {torch.cuda.device_count()} GPUs!",
            style="bold cyan",
        )
        model = TransparentDataParallel(model)
    return model


def make_optimizer(
    optimizer_partial: Partial[torch.optim.Optimizer], model: torch.nn.Module
) -> torch.optim.Optimizer:
    return optimizer_partial(model.parameters())


def make_scheduler(
    scheduler_partial: Partial[torch.optim.lr_scheduler.LRScheduler],
    optimizer: torch.optim.Optimizer,
    epochs: int,
) -> torch.optim.lr_scheduler.LRScheduler:
    scheduler = scheduler_partial(
        optimizer
    )  # TODO: less hacky way to set T_max for CosineAnnealingLR?
    if isinstance(scheduler, torch.optim.lr_scheduler.CosineAnnealingLR):
        scheduler.T_max = epochs
    return scheduler


def make_training_loss(
    training_mode: bool, training_loss_partial: Partial[torch.nn.Module]
):
    training_loss: Optional[torch.nn.Module] = None
    if training_mode:
        training_loss = training_loss_partial()
    return training_loss
