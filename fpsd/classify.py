import datetime
import matplotlib.pyplot as plt
import numpy as np
import multiprocessing
import pickle
from sklearn import (cross_validation, ensemble, metrics, svm, tree,
                     linear_model, neighbors, naive_bayes,
                     preprocessing)


import evaluation, database


def imputation(df):
    """Handle missing values in our data. This is mostly a
    placeholder for when we have a better way to handle this.

    Args:
        df [pandas DataFrame]: input data with NaNs

    Returns:
        df [pandas DataFrame]: output data with NaNs filled to 0
    """

    return df.fillna(0)


class Experiment:
    def __init__(self, model_timestamp, world, model_type, 
                 hyperparameters, feature_scaling=True,
                 n_cores=multiprocessing.cpu_count(), k=10):
        """
        Args:
            model [string]: machine learning algorithm to be used
            parameters [dict]: hyperparameter set to be used for the
                               machine learning algorithm
            k [int]: number of k-folds
            world [dict]: world type (open- or closed- world)
                          and parameters if necessary
        """

        self.model_timestamp = model_timestamp
        self.hyperparameters = hyperparameters
        self.model_type = model_type
        self.world_type = world["type"]
        self.frac_obs = world["observed_fraction"]
        self.n_cores = n_cores
        self.k = k
        self.feature_scaling = feature_scaling
        self.db = database.ModelStorage()
        self.train_class_balance = 'DEFAULT'
        self.base_rate = 'DEFAULT'

    def train_single_fold(self, x_train, y_train):
        """Trains a model and saves it as self.trained_model

        Args:
            x_train [ndarray]: features in training set (no id column, no target)
            y_train [ndarray]: target variable in training set (no id column)
        """

        print("Training {} classifier with {}".format(self.model_type,
                                                      self.hyperparameters))

        modelobj = self._get_model_object(self.model_type,
                                          self.hyperparameters,
                                          self.n_cores)
        trained_model = modelobj.fit(x_train, y_train)
        return trained_model

    def score(self, x_test, trained_model):
        """Generates continuous risk scores for a testing set.

        Args:
            x_test [ndarray]: testing features
            trained_model [sklearn object]: trained classifier object

        Returns:
            result_y [ndarray]: predictions on test set
        """

        result_y = trained_model.predict_proba(x_test)
        score_positive_class = result_y[:, 1]
        return score_positive_class

    def train_eval_all_folds(self, x_val, y_val):
        """Trains and evaluates models over all folds.

        Args:
            timestamp [string]: timestamp of the time the model is run,
                                used as model identifier
            x_val [ndarray]: feature matrix
            y_val [ndarray]: label vector

        Returns:
            auc [float]: area under the ROC curve
            mean_fpr [list of floats]: false positive rate averaged over
                                       all kfolds
            mean_tpr [list of floats]: true positive rate averaged over
                                       all kfolds
            trained_model [sklearn object]: trained object to be pickled
                                            so that it can be used for
                                            scoring 
        """

        if self.world_type == "closed":
            # Why we use stratified k-fold here:
            # http://stats.stackexchange.com/questions/49540/understanding-stratified-cross-validation
            cv = cross_validation.StratifiedKFold(y_val, n_folds=self.k,
                                                  shuffle=True)
        elif self.world_type == "open":
            pass  # TODO

        fpr_arr, tpr_arr, metrics_all_folds = [], [], []
        for i, (train, test) in enumerate(cv):

            fold_timestamp = datetime.datetime.now().isoformat()
            y_train, y_test = y_val[train], y_val[test]

            if self.feature_scaling:
                scaler = preprocessing.StandardScaler().fit(x_val[train])
                x_train = scaler.transform(x_val[train])
                x_test = scaler.transform(x_val[test])
            else:
                x_train, x_test = x_val[train], x_val[test]

            trained_model = self.train_single_fold(x_train, y_train)
            pred_probs = self.score(x_test, trained_model)

            filename_kfold = '{}_{}_undefended_frontpage_{}_model_{}_fold_{}_world.pkl'.format(
                fold_timestamp, self.model_timestamp, self.model_type,  i, self.world_type)
            fold_to_save = {'trained_object': trained_model,
                            'y_true': y_test, 'y_predicted': pred_probs}
            self.pickle_results(filename_kfold, fold_to_save)

            # Metrics computation
            # Compute ROC curve and area under the ROC curve
            eval_metrics = evaluation.get_metrics(y_test, pred_probs)
            metrics_all_folds.append(eval_metrics)
            fpr_arr.append(eval_metrics['fpr'])
            tpr_arr.append(eval_metrics['tpr'])

            # Save results of metrics in database
            self.db.save_fold_of_model(eval_metrics, self.model_timestamp, fold_timestamp)

        auc = evaluation.plot_allkfolds_ROC(self.model_timestamp, cv,
                                            fpr_arr, tpr_arr)

        print("Classifier {} trained! AUC: {}".format(self.model_timestamp,
                                                      auc))

        avg_metrics = evaluation.get_average_metrics(metrics_all_folds)
        # Save results of experiment (model evaluation averaged over all
        # folds) into the database
        self.db.save_full_model(avg_metrics, self.model_timestamp, self.__dict__)

    def pickle_results(self, pkl_file, to_save):
        with open(pkl_file, 'wb') as f:
            pickle.dump(to_save, f, protocol=pickle.HIGHEST_PROTOCOL)

    def _get_model_object(self, model, parameters, n_cores):
        """This method takes the requested model type and
        hyperparameters and produces the relevant classifier object.

        Returns:
            object with the fit() and predict_proba() methods
            implemented on it
        """

        if self.model_type == "RandomForest":
            return ensemble.RandomForestClassifier(
                n_estimators=self.hyperparameters['n_estimators'],
                max_features=self.hyperparameters['max_features'],
                criterion=self.hyperparameters['criterion'],
                max_depth=self.hyperparameters['max_depth'],
                min_samples_split=self.hyperparameters['min_samples_split'],
                n_jobs=self.n_cores)

        elif self.model_type == "RandomForestBagging":
            return ensemble.BaggingClassifier(
                ensemble.RandomForestClassifier(
                    n_estimators=self.hyperparameters['n_estimators'],
                    max_features=self.hyperparameters['max_features'],
                    criterion=self.hyperparameters['criterion'],
                    max_depth=self.hyperparameters['max_depth'],
                    min_samples_split=self.hyperparameters['min_samples_split'],
                    n_jobs=self.n_cores),
                #Bagging parameters
                n_estimators=self.hyperparameters['n_estimators_bag'],
                max_samples=self.hyperparameters['max_samples'],
                max_features=self.hyperparameters['max_features_bag'],
                bootstrap=self.hyperparameters['bootstrap'],
                bootstrap_features=self.hyperparameters['bootstrap_features'],
                n_jobs=self.n_cores
                )

        elif self.model_type == "RandomForestBoosting":
            return ensemble.AdaBoostClassifier(
                ensemble.RandomForestClassifier(
                    n_estimators=self.hyperparameters['n_estimators'],
                    max_features=self.hyperparameters['max_features'],
                    criterion=self.hyperparameters['criterion'],
                    max_depth=self.hyperparameters['max_depth'],
                    min_samples_split=self.hyperparameters['min_samples_split'],
                    n_jobs=self.n_cores),
                #Boosting parameters
                learning_rate=self.hyperparameters['learning_rate'],
                algorithm=self.hyperparameters['algorithm'],
                n_estimators=self.hyperparameters['n_estimators_boost']
                )

        elif self.model_type == 'SVM':
            return svm.SVC(C=self.hyperparameters['C_reg'],
                           kernel=self.hyperparameters['kernel'],
                           probability=True)

        elif self.model_type == 'LogisticRegression':
            return linear_model.LogisticRegression(
                C=self.hyperparameters['C_reg'],
                penalty=self.hyperparameters['penalty'])

        elif self.model_type == 'AdaBoost':
            return ensemble.AdaBoostClassifier(
                learning_rate=self.hyperparameters['learning_rate'],
                algorithm=self.hyperparameters['algorithm'],
                n_estimators=self.hyperparameters['n_estimators'])

        elif self.model_type == 'ExtraTrees':
            return ensemble.ExtraTreesClassifier(
                n_estimators=self.hyperparameters['n_estimators'],
                max_features=self.hyperparameters['max_features'],
                criterion=self.hyperparameters['criterion'],
                max_depth=self.hyperparameters['max_depth'],
                min_samples_split=self.hyperparameters['min_samples_split'],
                n_jobs=self.n_cores)

        elif self.model_type == 'GradientBoostingClassifier':
            return ensemble.GradientBoostingClassifier(
                n_estimators=self.hyperparameters['n_estimators'],
                learning_rate=self.hyperparameters['learning_rate'],
                subsample=self.hyperparameters['subsample'],
                max_depth=self.hyperparameters['max_depth'])

        elif self.model_type == 'GaussianNB':
            return naive_bayes.GaussianNB()

        elif self.model_type == 'DecisionTreeClassifier':
            return tree.DecisionTreeClassifier(
                max_features=self.hyperparameters['max_features'],
                criterion=self.hyperparameters['criterion'],
                max_depth=self.hyperparameters['max_depth'],
                min_samples_split=self.hyperparameters['min_samples_split'])

        elif self.model_type == 'SGDClassifier':
            return linear_model.SGDClassifier(
                loss=self.hyperparameters['loss'],
                penalty=self.hyperparameters['penalty'],
                n_jobs=self.n_cores)

        elif self.model_type == 'KNeighborsClassifier':
            return neighbors.KNeighborsClassifier(
                n_neighbors=self.hyperparameters['n_neighbors'],
                weights=self.hyperparameters['weights'],
                algorithm=self.hyperparameters['algorithm'],
                n_jobs=self.n_cores)

        else:
            raise ValueError("Unsupported classifier {}".format(self.model_type))
