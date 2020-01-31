import sklearn.metrics as metrics
import numpy as np
from itertools import combinations

def inter_intra_mean_ratio(data, labels, metric='euclidean'):
    """Clustering metric comparing mean pairwise distances, inter- vs intra-cluster
    
    Parameters
    ----------
    data : 2d array
        samples x features
    labels : 1d array
        cluster labels for each sample
    metric: string (default='euclidean')
        distance metric to use
    Returns
    -------
    float
        inter/intra distance ratio
    """    
    dist = metrics.pairwise_distances(data, metric=metric)
    intra = np.mean([
        np.mean([dist[x,y] for x,y in combinations(np.flatnonzero(labels==i),2)]) 
        for i in np.unique(labels)])
    inter = np.mean([
        np.mean(dist[np.ix_(labels==i, labels==j)]) 
        for i,j in combinations(np.unique(labels),2)])
    return inter/intra

def cv_confusion_matrix(X, y, classifier, cv):
    output = []
    for train, test in cv.split(X, y):
        classifier.fit(X[train,:], y[train])
        output.append(metrics.confusion_matrix(y[test], classifier.predict(X[test])))
    cm = np.mean(output, axis=0)
#     cm = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis]
    cm = cm/cm.sum()
    return cm
