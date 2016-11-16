import numpy as np
from scipy import interp
from sklearn import metrics
import pandas as pd
import pdb

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

THRESHOLDS = [0.01, 0.05, 0.1, 0.5, 1, 5, 10]

def get_metrics(truth, predicted):
    """Compute evaluation metrics for a given fold

    Args:
        truth [list]: List of labels
        predicted [list]: List of predicted scores

    Returns:
        eval_metrics [dict]: dict of metrics to be saved in the db
    """

    eval_metrics = {}
    fpr, tpr, thresholds = metrics.roc_curve(truth, predicted)
    eval_metrics["fpr"] = fpr
    eval_metrics["tpr"] = tpr
    eval_metrics["thresholds"] = thresholds
    eval_metrics["auc"] = metrics.auc(fpr, tpr)
    eval_metrics["precision"] = {}  # TODO
    eval_metrics["recall"] = {}  # TODO
    eval_metrics["f1"] = {}  # TODO

    for threshold in THRESHOLDS:
        precision, recall, f1 = precision_recall_at_x_proportion(truth,
            predicted, x_proportion=threshold/100)
        eval_metrics.update({threshold: {'precision': precision, 
                                         'recall': recall,
                                         'f1': f1}})
    return eval_metrics


def get_average_metrics(metrics_list):
    """Get algorithm performance over all folds"""

    eval_metrics = {}

    track_metric = 0
    for fold in metrics_list:
        track_metric += fold["auc"]

    # Divide by number of folds
    track_metric /= len(metrics_list)
    eval_metrics.update({"auc": track_metric})

    for metric in ("fpr", "tpr"):
        # the fpr, tpr output from scikit-learn may not have the same
        # number of elements in the arrays, set to Null for now
        eval_metrics.update({metric: [0, 0]})  # TODO

    for threshold in THRESHOLDS:
        eval_metrics[threshold] = {}
        for metric in ("precision", "recall", "f1"):
            track_metric = 0
            for fold in metrics_list:
                track_metric += fold[threshold][metric]

            # Divide by number of folds
            track_metric /= len(metrics_list)
            eval_metrics[threshold].update({metric: track_metric})

    return eval_metrics 


def precision_recall_at_x_proportion(test_labels, test_predictions, x_proportion=0.01,
                                     return_cutoff=False):
    """Compute precision, recall, F1 for a specified fraction of the test set.

    :params list test_labels: true labels on test set
    :params list test_predicted: predicted labels on test set
    :params float x_proportion: proportion of the test set to flag
    :params bool return_cutoff: if True return the cutoff probablility
    :returns float precision: fraction correctly flagged
    :returns float recall: fraction of the positive class recovered
    :returns float f1: 
    """

    cutoff_index = int(len(test_predictions) * x_proportion)
    cutoff_index = min(cutoff_index, len(test_predictions) - 1)

    sorted_by_probability = np.sort(test_predictions)[::-1]
    cutoff_probability = sorted_by_probability[cutoff_index]

    test_predictions_binary = [1 if x > cutoff_probability else 0 for x in test_predictions]

    precision, recall, f1, _ = metrics.precision_recall_fscore_support(
        test_labels, test_predictions_binary)

    # Only interested in metrics for label 1
    precision, recall, f1 = precision[1], recall[1], f1[1]

    if return_cutoff:
        return precision, recall, f1, cutoff_probability
    else:
        return precision, recall, f1


def plot_ROC(test_labels, test_predictions):
    fpr, tpr, thresholds = metrics.roc_curve(
        test_labels, test_predictions, pos_label=1)
    auc = "%.2f" % metrics.auc(fpr, tpr)
    title = 'ROC Curve, AUC = '+str(auc)
    with plt.style.context(('ggplot')):
        fig, ax = plt.subplots()
        ax.plot(fpr, tpr, "#000099", label='ROC curve')
        ax.plot([0, 1], [0, 1], 'k--', label='Baseline')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.legend(loc='lower right')
        plt.title(title)
    return fig


def plot_allkfolds_ROC(timestamp, cv, fpr_arr, tpr_arr):

    sns.set(style="white", palette="muted", color_codes=True)

    mean_tpr = 0.0
    mean_fpr = 0.0
    all_roc_auc = []
    bins_roc = np.linspace(0, 1, 300)
    with plt.style.context(('seaborn-muted')):
        fig, ax = plt.subplots(figsize=(10, 8))
        for i, (train, test) in enumerate(cv):
            mean_tpr += interp(bins_roc, fpr_arr[i], tpr_arr[i])
            mean_tpr[0] = 0.0
            mean_fpr += interp(bins_roc, fpr_arr[i], tpr_arr[i])
            mean_fpr[0] = 0.0
            roc_auc = metrics.auc(fpr_arr[i], tpr_arr[i])
            all_roc_auc.append(roc_auc)
            ax.plot(fpr_arr[i], tpr_arr[i], lw=1, label='KFold %d (AUC = %0.2f)' % (i, roc_auc))
        ax.plot([0, 1], [0, 1], '--', color=(0.6, 0.6, 0.6), label='Random')

        mean_tpr /= len(cv)
        mean_tpr[-1] = 1.0
        mean_auc = np.mean(all_roc_auc)
        ax.plot(bins_roc, mean_tpr, 'k--',
             label='Mean ROC (AUC = %0.2f)' % mean_auc, lw=2)

        ax.set_xlim([-0.05, 1.05])
        ax.set_ylim([-0.05, 1.05])
        ax.set_xlabel('False Positive Rate')
        ax.set_ylabel('True Positive Rate')
        ax.set_title('Receiver Operating Characteristic')
        ax.legend(loc="lower right")
        plt.savefig('{}_roc.png'.format(timestamp))
    plt.close('all') 
    return mean_auc


def get_feature_importances(model):

    try:
        return model.feature_importances_
    except:
        pass
    try:
        # Must be 1D for feature importance plot
        if len(model.coef_) <= 1:
            return model.coef_[0]
        else:
            return model.coef_
    except:
        pass
    return None


def plot_feature_importances(feature_names, feature_importances, N=30):
    importances = list(zip(feature_names, list(feature_importances)))
    importances = pd.DataFrame(importances, columns=["Feature", "Importance"])
    importances = importances.set_index("Feature")

    # Sort by the absolute value of the importance of the feature
    importances["sort"] = abs(importances["Importance"])
    importances = importances.sort(columns="sort", ascending=False).drop("sort", axis=1)
    importances = importances[0:N]

    # Show the most important positive feature at the top of the graph
    importances = importances.sort(columns="Importance", ascending=True)

    with plt.style.context(('ggplot')):
        fig, ax = plt.subplots(figsize=(16,12))
        ax.tick_params(labelsize=16)
        importances.plot(kind="barh", legend=False, ax=ax)
        ax.set_frame_on(False)
        ax.set_xlabel("Relative importance", fontsize=20)
        ax.set_ylabel("Feature name", fontsize=20)
    plt.tight_layout()
    plt.title("Most important features for attack", fontsize=20).set_position([.5, 0.99])
    return fig