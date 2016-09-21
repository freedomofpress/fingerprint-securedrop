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