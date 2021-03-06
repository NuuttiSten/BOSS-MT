import numpy as np
import pandas as pd
import json
import matplotlib.pyplot as plt
from scipy.stats import pearsonr, wilcoxon, mannwhitneyu
import scipy.stats as ss
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline



def loewner(A, B):
    """
    Return true, if A>=B
    where >= is loewner order (matrix comparison) 
    if A>=B, A spans over B
    used to detect poor fits of coregionalization
    if [coregionalization matrix] > [measured covariance]is broken, 
    covariance matrix is overestimated / fitted poorly
    """
    ret_list = []
    for b in B:
        D = (A-b).reshape((2,2))
        det = np.linalg.det(D)
        ret = 1
        if det < 0 or D[0,0] < 0:
            ret = 0
        ret_list.append(ret)
    return ret_list

## compare each number of secondary initpts
## to baseline with wilcoxon 2 sample signed rank test to see 
## when TL is faster than the baseline, also collect the lowest, 
## highest, median and mean expected improvement and their secondary initpts

def indicator_loss(b_times, r_times, N = None, alpha = 0.1, method = mannwhitneyu):
    """
    do wilxocon test to see if b_times - r_times median is less than 0
    H0: it is
    """
    if N is None:
        N = min([len(b_times), len(r_times)])*5
    b = np.random.choice(b_times, size = N, replace = True)
    r = np.random.choice(r_times, size = N, replace = True)
    #diff = b-r
    #diff = diff[diff != 0]
    # is the median of the differences b-r less than zero
    test = method(b,r, alternative = 'less')
    if test[1] < alpha:
        # reject
        return False
    else:
        return True

def loss_function_table(c_speed, name):
    """
    Sample n convergence speed results from baseline (b_times)
    and experiment with k secondary points (r_times)
    With wilcoxon 2 sample signed rank test determine, 
    if TL is faster than the baseline with that many secondary initpts
    return true
    else false
    """
    initpts_list = np.unique(c_speed[:,0]).reshape(-1,1)
    initpts_list = initpts_list[initpts_list != 0] # remove baselines
    b_times = c_speed[c_speed[:,0] == 0,1]
    b_mean = np.mean(b_times)
    faster = [] # which number of secondary initpts are faster than the baseline
    for initpts in initpts_list:
        r_times = c_speed[c_speed[:,0] == initpts, 1]
        #median_ixd = np.argsort(r_times)[len(r_times)//2]
        # add initpts, mean (loss function), wx test (indicator loss function) if faster than baseline
        faster.append([initpts, round(np.mean(r_times)/b_mean, 2), indicator_loss(b_times, r_times)])
    faster = np.array(faster).reshape(-1, 3)
    ret = pd.DataFrame({'experiment':name,
                        'secondary_initpts':faster[:,0],
                       'mean_loss':faster[:,1],
                       'indicator_loss':faster[:,2]})
    # normalize mean acquisition time
    # loss function minima -> 
    # plot loss function minima against number of secondary initpts
    return ret
        
## plot convergence and collect loss function table
def plot_TL_convergence(filename, experiment_folders, baseline_folders):
    """
    Plot for list of TL experiments:
    convergence speed to 0.1 kcal/mol in
    - BO iterations and CPU time
    - mean of both (statistical expected value)
    - linear trend
    """
    cputime_max = 0
    N = len(experiment_folders)
    fig, axs = plt.subplots(2,N,
                    figsize = (5*N,10),
                    sharey = 'row')
    SMALL_SIZE = 15
    MEDIUM_SIZE = 20
    LARGE_SIZE = 25
    tot_loss_table = None
    for i in range(N):
        experiment = experiment_folders[i].copy()
        baseline = baseline_folders[i].copy()

        explist = baseline
        for exp in experiment:
            explist.append(exp)


        convergence_iterations = []
        convergence_times = []

        for exp in explist:
            if len(exp['initpts'])>1:
                secondary_initpts = int(exp['initpts'][1])
            else:
                secondary_initpts = 0
            # convergence by iteration
            convergence_iter = exp['iterations_to_gmp_convergence'][5]
            convergence_iterations.append([secondary_initpts,convergence_iter])
            # convergence by cpu time
            convergence_time = exp['totaltime_to_gmp_convergence'][5]
            convergence_times.append([secondary_initpts, convergence_time])
            
           

        # plot
        convergence_iterations = np.array(convergence_iterations, dtype = float)
        axs[0, i].scatter(convergence_iterations[:,0],
                          convergence_iterations[:,1],
                    color = 'blue', alpha = 0.5, marker = 'x',
                         label = 'observation')

        # linear fit
        raw_rows = convergence_iterations
        clean_rows = raw_rows[np.logical_not(np.logical_or(np.isnan(raw_rows[:,0]),
                                                           np.isnan(raw_rows[:,1]))),:]
        x_train = clean_rows[:,0].reshape(-1,1)
        y_train = clean_rows[:,1].reshape(-1,1)
        reg = LinearRegression().fit(x_train, y_train)
        x = np.unique(convergence_iterations[:,0]).reshape(-1,1)
        y = reg.predict(x)
        axs[0, i].plot(x,y, color = 'red', label = 'trend', linewidth = 3)
        # plot means
        mean_labelled = False
        for initpts in np.unique(x_train):
            mean = np.mean(y_train[x_train == initpts])
            if mean_labelled:
                axs[0,i].scatter([initpts], [mean], color = 'red', marker = 's')
            else:
                axs[0,i].scatter([initpts], [mean],
                                 color = 'red', marker = 's',
                                label = 'mean')
                mean_labelled = True
        axs[0,i].legend(fontsize = SMALL_SIZE)

        ###
        convergence_times = np.array(convergence_times, dtype = float)
        axs[1, i].scatter(convergence_times[:,0],
                          convergence_times[:,1],
                    color = 'blue', alpha = 0.5, marker = 'x',
                         label = 'observation')
        ### linear fit
        raw_rows = convergence_times
        clean_rows = raw_rows[np.logical_not(np.logical_or(np.isnan(raw_rows[:,0]),
                                                           np.isnan(raw_rows[:,1]))),:]
        clean_rows = clean_rows.reshape(-1,2)
        #outliers = clean_rows[clean_rows[:,1] > cputime_max,:]
        # outlier if more than 2 stds off the mean
        outlier_idx = []
        for row in clean_rows:
            initpts = row[0]
            val = row[1]
            obs = clean_rows[clean_rows[:,0] == initpts,:]
            #obs = obs[obs != row]
            m = np.mean(obs)
            sd = np.std(obs)
            if (val - m) / sd > 2.5: # z-score - assuming normal
                # distribution only 0.5% of data should be at least this far
                outlier_idx.append(True)
            else:
                outlier_idx.append(False)
        outliers = clean_rows[outlier_idx, :]
        #clean_rows = clean_rows[clean_rows[:,1] <= cputime_max, :]
        clean_rows = clean_rows[np.logical_not(outlier_idx),:]
        if max(clean_rows[:,1]) > cputime_max:
            cputime_max = max(clean_rows[:,1])
        x_train = clean_rows[:,0].reshape(-1,1)
        y_train = clean_rows[:,1].reshape(-1,1)

        degree=1
        polyreg=make_pipeline(PolynomialFeatures(degree),LinearRegression())
        polyreg.fit(x_train,y_train)

        x = np.unique(convergence_iterations[:,0]).reshape(-1,1)
        axs[0,i].set_xticks(x[::2])
        y = polyreg.predict(x)
        axs[1, i].plot(x,y, color = 'red', label = 'trend', linewidth = 3)
        axs[1,i].set_xticks(x[::2])
        outlier_labelled = False
        for outlier in outliers:
            if outlier_labelled:
                axs[1,i].scatter([outlier[0]],[cputime_max*1.1],
                             marker = 6, color = 'black')
            else:
                axs[1,i].scatter([outlier[0]],[cputime_max*1.1],
                             marker = 6, color = 'black',
                            label = 'outlier')
                outlier_labelled = True
            axs[1,i].annotate('{:.0f}'.format(outlier[1]), 
                              [outlier[0],cputime_max*1.1], rotation = 270,
                              fontsize = SMALL_SIZE)
        mean_labelled = False
        for initpts in np.unique(x_train):
            mean = np.mean(y_train[x_train == initpts])
            if mean_labelled:
                axs[1,i].scatter([initpts], [mean], color = 'red', marker = 's')
            else:
                axs[1,i].scatter([initpts], [mean],
                                 color = 'red', marker = 's',
                                label = 'mean')
                mean_labelled = True
        axs[1,i].legend(fontsize = SMALL_SIZE)

        expname = experiment_folders[i][0]['name'].split('_')[0]
        title = f'{i+1}a) {expname}'
        axs[0,i].set_title(title, loc = 'left', fontsize = LARGE_SIZE)
        title = f'{i+1}b) {expname}'
        axs[1,i].set_title(title, loc = 'left', fontsize = LARGE_SIZE)

        # collect table of loss function values
        c_speed = clean_rows
        loss_table = loss_function_table(c_speed, expname)
        
        if tot_loss_table is None:
            tot_loss_table = loss_table
        else:
            tot_loss_table = pd.concat([tot_loss_table,loss_table], axis = 0)

    axs[0,0].set_ylabel('BO iterations to GMP convergence', fontsize = SMALL_SIZE)
    axs[1,0].set_ylabel('CPU time to GMP convergence', fontsize = SMALL_SIZE)

    axs[1,0].set_ylim(-0.05*cputime_max,1.4*cputime_max)

    for ax in axs[1,:]:
        ax.set_xlabel('secondary initpts', fontsize = SMALL_SIZE)

    for ax in axs.flatten():
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['top'].set_visible(False)
        ax.tick_params('x',labelrotation = 40)
        ax.tick_params(axis = 'both',
              width = 3, length = 4,
              labelsize = SMALL_SIZE)

    plt.savefig(filename)
    
    return tot_loss_table
    