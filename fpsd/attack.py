import argparse
import datetime
from itertools import product
import pdb
import pickle
import yaml

import classify, database


def run(options):
    """Takes an attack file, gets the features, and runs all experiments
    and saves the output in the database.

    Args:
        options [dict]: attack setup file
    """

    with open(options, 'r') as f:
        options = yaml.load(f)

    db = database.DatasetLoader()

    if options["world"]["type"] == "closed":
        df = db.load_closed_world()
    elif options["world"]["type"] == "open":
        df = db.load_open_world()

    df = classify.interpolate(df)
    x = df.drop(['exampleid', 'is_sd'], axis=1).values
    y = df['is_sd'].astype(int).values

    experiments = generate_experiments(options)
    for experiment in experiments:
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
    parser.add_argument("-a", "--setup-yml", dest="attack_setup", type=str, default="attack.yaml", 
                        help="point to attack setup file")
    args = parser.parse_args()

    run(args.attack_setup)
