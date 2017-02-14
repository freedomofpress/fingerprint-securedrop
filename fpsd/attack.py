#!/usr/bin/env python3.5
import argparse
import datetime
from itertools import product
import pickle
import yaml

import classify, database


def run(options):
    """Takes an attack file, gets the features, and runs all experiments
    and saves the output in the database.

    Args:
        options [dict]: attack setup file
    """

    with open(options) as f:
        options = yaml.load(f)

    db = database.DatasetLoader()

    df = db.load_world(options["world"]["type"])

    df = classify.imputation(df)
    # wa_knn_df = classify.imputation(df, -1)

    x = df.drop(['exampleid', 'is_sd'], axis=1).values
    # wa_knn_x = wa_knn_df.drop(['exampleid', 'is_sd'], axis=1).values
    y = df['is_sd'].astype(int).values
    # wa_knn_y = wa_knn_df['is_sd'].astype(int).values


    for experiment in generate_experiments(options):
        # if experiment['model_type'] = 'Wa-kNN':
        #     experiment.train_eval_all_folds(wa_knn_x, wa_knn_y)
        # else:
        experiment.train_eval_all_folds(x, y)


def generate_experiments(options):
    """Takes an attack file and generates all the experiments that
    should be run 

    Args:
        options [dict]: attack setup file

    Returns:
        all_experiments [list]: list of Experiment objects
    """

    all_experiments = []

    for model in options["models"]:
        model_hyperparameters = options["parameters"][model]

        parameter_names = sorted(model_hyperparameters)
        parameter_values = [model_hyperparameters[p] for p in parameter_names]

        # Compute Cartesian product of hyperparameter lists
        all_params = product(*parameter_values)

        for param in all_params:
            parameters = {name: value for name, value
                              in zip(parameter_names, param)}

            timestamp = datetime.datetime.now().isoformat()

            all_experiments.append(classify.Experiment(
                                model_timestamp=timestamp,
                                world=options["world"],
                                model_type=model,
                                hyperparameters=parameters,
                                feature_scaling=options["feature_scaling"]))
    return all_experiments


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", dest="config", type=str,
                        default="attack.yml",
                        help="point to attack config/setup file")
    args = parser.parse_args()

    run(args.config)
