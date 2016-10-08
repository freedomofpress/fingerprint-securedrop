# Adding Features

Writing a new feature can be done by adding a method in `fpsd/features.py`.

# Adding Classifiers

A new classifier can be added by adding a new stanza in the `Experiment._get_model_object()` method in `classify.py`. This method must return an object that has the `fit()` - model training - and `predict_proba()` - predict scores on test set - methods defined on it. It expects these methods because that is what scikit-learn uses for its classifier objects. 

To get the code to use the classifier, add a string corresponding to its name to your attack YAML file under `models` and add any hyperparameters and options (e.g. number of rounds for Wa-kNN) under `parameters`. 