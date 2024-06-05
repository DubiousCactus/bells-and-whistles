#! /usr/bin/env python3
# vim:fenc=utf-8
#
# Copyright © 2023 Théo Morales <theo.morales.fr@gmail.com>
#
# Distributed under terms of the MIT license.


from hydra_zen import store, zen

import conf.experiment  # Must import the config to add all components to the store! # noqa
from bootstrap.launch_experiment import launch_experiment
from conf import project as project_conf
from utils import seed_everything

if __name__ == "__main__":

    def set_test_mode(cfg):
        cfg.run.training_mode = False

    "============ Hydra-Zen ============"
    store.add_to_hydra_store(
        overwrite_ok=True
    )  # Overwrite Hydra's default config to update it
    zen(
        launch_experiment,
        pre_call=[
            lambda cfg: seed_everything(
                cfg.run.seed
            )  # training is the config of the training group, part of the base config
            if project_conf.REPRODUCIBLE
            else lambda: None,
            set_test_mode,
        ],
    ).hydra_main(
        config_name="base_experiment",
        version_base="1.3",  # Hydra base version
    )
