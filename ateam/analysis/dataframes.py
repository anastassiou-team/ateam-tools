"""Module for analysing and plotting data in pandas dataframes.
"""
import warnings
import numpy as np
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.stats import multitest
from scipy.stats import mannwhitneyu, linregress
from itertools import combinations
from six import string_types

from future.standard_library import install_aliases
install_aliases()
from collections import UserString

class LabeledVar(UserString):
    def __init__(self, string=None, label=None):
        super(LabeledVar, self).__init__(string)
        self.label = label or string

# Restructuring commands
# 

def flatten_columns(df):
    """Flatten a dataframe with hierarchically indexed columns
    by concatenating labels across levels with underscores 
    """
    df = df.copy()
    df.columns = [col if isinstance(col, string_types) else '_'.join(col).rstrip('_') 
        for col in df.columns.values]
    return df

def summary(series):
    """Aggregation function, summarizes a series by the number of values, or the single shared value if constant
    """
    unique = series.unique()
    if len(unique)==1:
        out = unique[0]
    else:
        out = "{} values".format(len(unique))
    return out

def safe_join(dfa, dfb, **kwargs):
    """Join two dataframes, discarding columns in the second that are already in the first
    """
    return dfa.join(dfb[dfb.columns.difference(dfa.columns)], **kwargs)

def split_columns_by_groups(cells_fit_df, group_column, flatten=True):
    """Restructure dataframe by pivoting group column values to new level of column labels,
    optionally flattening the result (colA becomes colA_groupA, colA_groupB etc.).
    """
    # TODO: may only work if index is nonunique ID repeated across groups?
    cells_fit_df = cells_fit_df.set_index([group_column], append=True)
    cells_fit_df = cells_fit_df.unstack(level=group_column)
    # could check for distinct values first
    if flatten:
        cells_fit_df = flatten_columns(cells_fit_df)
    return cells_fit_df

# Plotting functions
# 
def scatterplot_fix(x=None, y=None, data=None, ypad=[], xpad=[], **kwargs):
    """Seaborn scatterplot with limits autoscaling fixed manually
    Default padding 5% of range
    """
    sns.scatterplot(x=x, y=y, data=data, **kwargs)
    ax = kwargs.get('ax') or plt.gca()
    if data is not None:
        xlabel, ylabel = x, y
        x = data[x]
        y = data[y]
        ax.set_xlabel(getattr(xlabel, "label", None) or xlabel)
        ax.set_ylabel(getattr(ylabel, "label", None) or ylabel)
    ax.set_xlim(*limits_pad(x, *xpad))
    ax.set_ylim(*limits_pad(y, *ypad))

def plot_reg_df(x, y, data=None, groups=None, showstats=True, pval=True, line_args={}, **kwargs):
    """Plot y vs. x regression and scatterplot from dataframe data
    If groups are specified, adjusts stats via cluster-robust covariance estimates.
    """
    import statsmodels.api as sm
    # remove color kwarg in favor of hue (in case using in seaborn grid)
    kwargs.pop('color',None)
    scatterplot_fix(x=x, y=y, data=data, ypad=(0.2, 0), **kwargs)

    xd = data[x]; yd = data[y]
    results = sm.OLS(yd, sm.add_constant(xd), hasconst=True).fit()
    if groups:
        group_ints = data[groups].astype('category').cat.codes
        results = results.get_robustcov_results(cov_type='cluster', groups=group_ints)
    xpred =  np.linspace(xd.min(), xd.max(), 50)
    ypred = results.predict(sm.add_constant(xpred))
    
    ax = kwargs.get('ax') or plt.gca()
    ax.plot(xpred, ypred, **line_args)

    summary = "$R^2={:.2g}$".format(results.rsquared)
    if pval=='log':
        summary += ", $log(p)={:.2g}$".format(np.log(results.pvalues[1]))
    elif pval:
        summary += ", $p={:.2g}$".format(results.pvalues[1])
    if showstats:
        ax.text(0.5, 0.99, summary, transform=ax.transAxes,
        verticalalignment='top', horizontalalignment='center')

def plot_grouped_corr(x, y, data, groups, **kwargs):
    """Plot y vs. x regression of group means from dataframe data,
    along with scatterplot of all data colored by group.
    Results should be directly comparable to plot_reg_df.
    kwargs pass through to seaborn scatterplot.
    """
    data = data.sort_values(groups)
    scatterplot_fix(x, y, data=data, hue=groups, legend=False, s=30, alpha=0.6, **kwargs)
    data = data.groupby(groups).mean().reset_index()
    plot_reg_df(x, y, data=data.dropna(subset=[x,y]), hue=groups, legend=False, s=100, pval=True, **kwargs)

def plot_category_df(x, y, data=None, ticks=False, **kwargs):
    """Plot regression against a categorical x variable.
    Args use seaborn plotting conventions
    """
    from statsmodels.formula.api import ols
    results = ols('{} ~ {}'.format(y, x), data=data).fit()
    # logp = np.log(results.f_pvalue)
    # summary = "$F={:.3g}$, $log(p)={:.3g}$".format(results.fvalue, logp)
    summary = "$R^2={:.2g}$".format(results.rsquared)

    sns.stripplot(x=x, y=y, data=data, palette='muted')
    plt.ylim(*limits_pad(data[y], 0.2, 0))
    ax = plt.gca()
    ax.text(0.5, 0.99, summary, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='center')
    if not ticks:
        plt.xticks([])

def limits_pad(data, upper=0.05, lower=None):
    xmin = data.min()
    xmax = data.max()
    lower = upper if lower is None else lower
    r = xmax-xmin
    return (xmin - lower*r, xmax + upper*r)

def boxplot(data, var, group, show_swarm=True):
    data = data[~data[var].isna()].sort_values(group)
    nobs = data.groupby(group)[var].count().apply(lambda n: "n={}".format(n))

    ax = sns.boxplot(x=group, y=var, data=data)
    if show_swarm:
        ax2 = sns.swarmplot(x=group, y=var, data=data, color=".01", ax=ax)

    ticks = [tick.get_text() + "\n" + nobs[i] for i, tick in enumerate(ax.get_xticklabels())]
    ax.set_xticklabels(ticks)
    return ax

def boxplot_with_mw_bars(data, var, group, pairs=None, cutoff=0.05, show_swarm=True):
    boxplot(data, var, group, show_swarm=show_swarm)
    pairs, pairs_idx, pvals = pairwise_mw(data, var, group, pairs)
    plot_sig_bars(pvals, pairs_idx, cutoff)

def plot_mw_bars(data, var, group, group_vals=None, pairs='all', cutoff=0.05, label='stars', ax=None, y0=None):
    group_vals = group_vals or data[group].unique().tolist()
    pairs_list, pairs_idx, pvals = pairwise_mw(data, var, group, group_vals, pairs)
    pvals = multitest.multipletests(pvals, method='fdr_bh')[1]
    y0 = data[ data[group].isin(set.union(*map(set,pairs_list))) ][var].max()
    plot_sig_bars(pvals, pairs_idx, cutoff, label=label, ax=ax, y0=y0)

def plot_sig_bars(pvals, pairs_idx, cutoff=0.05, label='stars', ax=None, y0=None):
    ax = ax or plt.gca()
    ylim = ax.get_ylim()
    pairs_sig = np.flatnonzero(np.array(pvals)<cutoff)
    
    y0 = y0 or ylim[0]
    n = len(pairs_sig)
    dy = 0.04*(ylim[1]-ylim[0]) # use 5% of y-axis range
    yvals = y0 + dy*np.arange(1, n+1)
    for i, pair in enumerate(pairs_sig):
        plot_sig_bar(pvals[pair], yvals[i], pairs_idx[pair], label=label, ax=ax)

def plot_sig_bar(pval, y, x_pair, label='stars', ax=None):
    ax = ax or plt.gca()
    ax.plot(x_pair, [y, y], 'grey')
    if label=='stars':
        text = np.choose(np.searchsorted([1e-3, 1e-2, 5e-2], pval), ['***','**','*',''])
    elif label=='pval':
        text = "p={p:.2}".format(p=pval)
    else:
        text = ''
    ax.text(np.mean(x_pair), y, text, horizontalalignment='center', verticalalignment='bottom')

def pairwise_mw(data, var, group, group_vals=None, pairs='all'):
    data = data[~data[var].isna()]#.sort_values(group)
    group_vals = group_vals or data[group].unique().tolist()
    # group_vals.sort()
    if pairs is 'all':
        pairs = list(combinations(group_vals, 2))
    pvals = []
    pairs_idx = []
    groups = data.groupby(group)[var]
    for pair in pairs:
        u, p = mannwhitneyu(groups.get_group(pair[0]), groups.get_group(pair[1]), alternative='two-sided')
        pvals.append(p)
        pairs_idx.append([group_vals.index(pair[0]), group_vals.index(pair[1])])
    return pairs, pairs_idx, pvals


# Analysis of two-variable relationships in dataframes
# 
def combine_functions_hierarchical(xvar, yvar, functions, dropna=True):
    """Constructs a single function, to be applied by DataFrame.apply,
    which returns output from several two-variable functions combined into a single hierarchically indexed dataframe.
    """
    def combined_fcn(df):
        x, y = trend_from_df(df, xvar, yvar, dropna=True)
        outputs = [pd.Series(function(x,y)) for function in functions]
        # Add labels by function as column multi-index?
        # keys = [function.__name__ for function in functions]
        # df_hierarch = pd.concat(outputs, axis=0, keys=keys, names=["analysis", "feature"])
        df_hierarch = pd.concat(outputs, axis=0, names=["analysis"])
        return df_hierarch
    return combined_fcn

def group_fit_df(df, xvar, yvar, by):
    """Calculate linear fit of two-variable trend independently for each group of data in dataframe 
    
    Arguments:
        xvar, yvar -- columns to fit
        by -- columns to group by
    """
#     to use multiple return values in apply(), create Series from dict
    fit_function = lambda df: pd.Series(linfit(*trend_from_df(df, xvar, yvar)))
    df_fit = df.groupby(by).apply(fit_function)
    return df_fit

def trend_from_df(df, xvar, yvar, dropna=True):
    """Extract a pair of columns from dataframe, filtering missing values by default
    """
    if dropna:
        df = df[~df[yvar].isna()]
    x = df[xvar]
    y = df[yvar]
    return x, y

# TODO: could optimize by dealing with sorted data only
def closest_value(x, y, x0):
    error_out = {'y0': np.nan}
    if not ((min(x)<x0) and (max(x)>x0)):
        return error_out
    i = np.argmin(np.abs(x-x0))
    y0 = np.mean(y[x==x[i]])
    return {'y0': y0}

def threshold(x, y, n_repeats=5):
    error_out = {'min': np.nan, 'mean': np.nan}
    if len(y)<n_repeats:
        return error_out
    x_mins = np.partition(x, n_repeats-1)[:n_repeats]
    return {'thresh_min': np.min(x_mins), 'thresh_mean': np.mean(x_mins)}
    
def linfit(x, y):
    error_out = {'slope':np.nan, 'yint':np.nan, 'xint':np.nan, 'error':np.nan, 'slope_rel':np.nan}
    try:
        if len(y)==0:
            return error_out
        slope, yint = linregress(x,y)[:2]
        xint = np.nan if slope==0 else -yint/slope
        yfit = slope*x + yint
        rmse = np.sqrt(np.mean( (y - yfit) ** 2))
        results = {'slope':slope, 'yint':yint, 'xint':xint, 'error':rmse, 'slope_rel':slope/yint}
    except Exception as e:
        warnings.warn(e)
        results = error_out
    return results