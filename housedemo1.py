# -*- coding: utf-8 -*-
"""
Created on Sat Dec 30 09:08:41 2017
data source---https://archive.ics.uci.edu/ml/machine-learning-databases/housing/housing.data
@author: YLi
"""



#define the issue
#connect the data source
#load the data

#understand data
#describe data by statistics
#viz data

#prepare data
#clean data
#feature selection
#convert data

#evaluate algorithm
#split data
#define model
#check algorithm
#compare algorithm

#optimize the model
#hyper parameter
#assemble algorithm

#result
#predict data
#use all data set to produce model
#sequenced model 

"""CRIM：城镇人均犯罪率。
ZN：住宅用地所占比例。
INDUS：城镇中非住宅用地所占比例。
CHAS：CHAS虚拟变量，用于回归分析。
NOX：环保指数。
RM：每栋住宅的房间数。
AGE：1940年以前建成的自住单位的比例。
DIS：距离5个波士顿的就业中心的加权距离。
RAD：距离高速公路的便利指数。
TAX：每一万美元的不动产税率。
PRTATIO：城镇中的教师学生比例。
B：城镇中的黑人比例。
LSTAT：地区中有多少房东属于低收入人群。
MEDV：自住房屋房价中位数"""

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import sklearn as sk
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.model_selection import KFold
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import GridSearchCV
from sklearn.linear_model import LinearRegression
from sklearn.linear_model import Lasso
from sklearn.linear_model import ElasticNet
from sklearn.tree import DecisionTreeRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.ensemble import AdaBoostRegressor
from sklearn.metrics import mean_squared_error 

filename='housing.csv'
names = ['CRIM', 'ZN', 'INDUS', 'CHAS', 'NOX', 'RM', 'AGE', 'DIS', 'RAD', 'TAX', 'PRTATIO', 'B', 'LSTAT', 'MEDV']
data = pd.read_csv(filename, names=names, delim_whitespace=True)

print(data.shape)
print(data.dtypes)

#check the first 30 line data
pd.set_option('display.line_width', 120)
print(data.head(30))

pd.set_option('precision', 1)
print(data.describe())

pd.set_option('precision', 2)
print(data.corr(method='pearson'))
data_corr=data.corr(method='pearson')

"""NOX与INDUS之间的皮尔逊相关系数是0.76。
DIS与INDUS之间的皮尔逊相关系数是-0.71。
TAX与INDUS之间的皮尔逊相关系数是0.72。
AGE与NOX之间的皮尔逊相关系数是0.73。
DIS与NOX之间的皮尔逊相关系数是-0.77"""

#单一特征图表
"""首先查看每一个数据特征单独的分布图，多查看几种不同的图表有助于发现更好的方法。
我们可以通过查看各个数据特征的直方图，来感受一下数据的分布情况"""

# 直方图
data.hist(sharex=False, sharey=False, xlabelsize=1, ylabelsize=1)
plt.show()

"""从图中可以看到有些数据呈指数分布，如CRIM、ZN、AGE和B;有些数据特征呈双峰分布，如RAD和TAX。"""

#通过密度图可以展示这些数据的特征属性，密度图比直方图更加平滑地展示了这些数据特征
# 密度图
data.plot(kind='density', subplots=True, layout=(4,4), sharex=False, fontsize=1)
plt.show()

#通过箱线图可以查看每一个数据特征的状况，也可以很方便地看出数据分布的偏态程度。代码如下：

#箱线图
data.plot(kind='box', subplots=True, layout=(4,4), sharex=False, sharey=False, fontsize=8)
plt.show()

#接下来利用多重数据图表来查看不同数据特征之间的相互影响关系。首先看一下散点矩阵图。代码如下：

# 散点矩阵图
pd.scatter_matrix(data)
plt.show()

"""通过散点矩阵图可以看到，虽然有些数据特征之间的关联关系很强，
但是这些数据分布结构也很好。即使不是线性分布结构，也是可以很方便进行预测的分布结构"""

#再看一下数据相互影响的相关矩阵图
fig=plt.figure()
ax=fig.add_subplot(111)
cax=ax.matshow(data.corr(), vmin=-1, vmax=1, interpolation='none')
fig.colorbar(cax)
ticks=np.arange(0,14,1)
ax.set_xticks(ticks)
ax.set_yticks(ticks)
ax.set_xticklabels(names)
ax.set_yticklabels(names)
plt.show()

"""根据图例可以看到，数据特征属性之间的两两相关性，有些属性之间是强相关的，
建议在后续的处理中移除这些特征属性，以提高算法的准确度"""

"""思路总结

通过数据的相关性和数据的分布等发现，数据集中的数据结构比较复杂，需要考虑对数据进行转换，以提高模型的准确度。
可以尝试从以下几个方面对数据进行处理：

通过特征选择来减少大部分相关性高的特征。
通过标准化数据来降低不同数据度量单位带来的影响。
通过正态化数据来降低不同的数据分布结构，以提高算法的准确度。
可以进一步查看数据的可能性分级(离散化)，它可以帮助提高决策树算法的准确度。"""

# 分离数据集
pd.array = data.values
X = pd.array[:, 0:13]
Y = pd.array[:, 13]
validation_size = 0.2
seed = 7
X_train, X_validation, Y_train, Y_validation = train_test_split(X, Y,test_size=validation_size, random_state=seed)


"""评估算法——原始数据

分析完数据不能立刻选择出哪个算法对需要解决的问题最有效。我们直观上认为，由于部分数据的线性分布，
线性回归算法和弹性网络回归算法对解决问题可能比较有效。另外，由于数据的离散化，
通过决策树算法或支持向量机算法也许可以生成高准确度的模型。到这里，依然不清楚哪个算法会生成准确度最高的模型，
因此需要设计一个评估框架来选择合适的算法。
我们采用10折交叉验证来分离数据，通过均方误差来比较算法的准确度。均方误差越趋近于0，算法准确度越高"""

# 评估算法 —— 评估标准
num_folds = 10
seed = 7
scoring = 'neg_mean_squared_error'

"""对原始数据不做任何处理，对算法进行一个评估，形成一个算法的评估基准。这个基准值是对后续算法改善优劣比较的基准值。
我们选择三个线性算法和三个非线性算法来进行比较。

线性算法：线性回归(LR)、套索回归(LASSO)和弹性网络回归(EN)。
非线性算法：分类与回归树(CART)、支持向量机(SVM)和K近邻算法(KNN)"""

#evaluation---baseline
models={}
models['LR']=LinearRegression()
models['LASSO']=Lasso()
models['EN']=ElasticNet()
models['KNN']=KNeighborsRegressor()
models['CART']=DecisionTreeRegressor()
models['SVM']=SVR()

#对所有的算法使用默认参数，并比较算法的准确度，此处比较的是均方误差的均值和标准方差

results=[]
for key in models:
    kfold=KFold(n_splits=num_folds, random_state=seed)
    cv_result=cross_val_score(models[key], X_train, Y_train, cv=kfold, scoring=scoring)
    results.append(cv_result)
    print('%s: %f (%f)' % (key, cv_result.mean(), cv_result.std()))
    
"""对所有的算法使用默认参数，并比较算法的准确度，此处比较的是均方误差的均值和标准方差"""

#viz and evalute all algorithm
def eval_models():
    fig=plt.figure()
    fig.suptitle('Algorithm Comparsion')
    ax=fig.add_subplot(111)
    plt.boxplot(results)
    ax.set_xticklabels(models.keys())
    plt.show()

eval_models()
"""不同的数据度量单位，也许是K近邻算法和支持向量机算法表现不佳的主要原因。下面将对数据进行正态化处理，再次比较算法的结果。

评估算法——正态化数据

在这里猜测也许因为原始数据中不同特征属性的度量单位不一样，导致有的算法的结果不是很好。接下来通过对数据进行正态化，
再次评估这些算法。在这里对训练数据集进行数据转换处理，将所有的数据特征值转化成“0”为中位值、标准差为“1”的数据。对数据正态化时，
为了防止数据泄露，采用Pipeline来正态化数据和对模型进行评估。为了与前面的结果进行比较，此处采用相同的评估框架来评估算法模型"""

pipelines={}
pipelines['ScalerLR']=Pipeline([('Scaler', StandardScaler()), ('LR', LinearRegression())])
pipelines['ScalerLASSO']=Pipeline([('Scaler', StandardScaler()), ('LASSO', Lasso())])
pipelines['ScalerEN']=Pipeline([('Scaler', StandardScaler()), ('EN', ElasticNet())])
pipelines['ScalerKNN']=Pipeline([('Scaler', StandardScaler()), ('KNN', KNeighborsRegressor())])
pipelines['ScalerCART']=Pipeline([('Scaler', StandardScaler()), ('CART', DecisionTreeRegressor())])
pipelines['ScalerSVM']=Pipeline([('Scaler', StandardScaler()), ('SVM', SVR())])

results=[]

for key in pipelines:
    kfold=KFold(n_splits=num_folds, random_state=seed)
    cv_result=cross_val_score(pipelines[key], X_train, Y_train, cv=kfold, scoring=scoring)
    results.append(cv_result)
    print('%s: %f (%f)' % (key, cv_result.mean(), cv_result.std()))

"""you see KNN has the best MSE"""

eval_models()


"""目前来看，K近邻算法对做过数据转换的数据集有很好的结果，
但是是否可以进一步对结果做一些优化呢?K近邻算法的默认参数近邻个数(n_neighbors)是5，下面通过网格搜索算法来优化参数"""

#tuning parameter in KNN

scaler = StandardScaler().fit(X_train)
rescaledX=scaler.transform(X_train)
param_grid={'n_neighbors':[1,3,5,7,9,11,13,15,17,19,21]}
model=KNeighborsRegressor()
kfold=KFold(n_splits=num_folds, random_state=seed)
grid=GridSearchCV(estimator=model, param_grid=param_grid, scoring=scoring, cv=kfold)
grid_result=grid.fit(X=rescaledX, y=Y_train)

print('Best: %s use %s' % (grid_result.best_score_, grid_result.best_params_))
cv_results=zip(grid_result.cv_results_['mean_test_score'], grid_result.cv_results_['std_test_score'], grid_result.cv_results_['params'])
for mean, std, param in cv_results:
    print('%f (%f) with %r' % (mean, std, param))

"""最优结果——K近邻算法的默认参数近邻个数(n_neighbors)是3"""

"""集成算法

除调参之外，提高模型准确度的方法是使用集成算法。下面会对表现比较好的线性回归、K近邻、分类与回归树算法进行集成，来看看算法能否提高。

装袋算法：随机森林(RF)和极端随机树(ET)。
提升算法：AdaBoost(AB)和随机梯度上升(GBM)。

依然采用和前面同样的评估框架和正态化之后的数据来分析相关的算法"""

ensembles={}
ensembles['ScaledAB']=Pipeline([('Scaler', StandardScaler()), ('AB', AdaBoostRegressor())])
ensembles['ScaledAB-KNN']=Pipeline([('Scaler', StandardScaler()), ('ABKNN', AdaBoostRegressor(base_estimator=KNeighborsRegressor(n_neighbors=3)))])
ensembles['Scaled-LR']=Pipeline([('Scaler', StandardScaler()), ('ABLR', AdaBoostRegressor(LinearRegression()))])
ensembles['ScaledRFR']=Pipeline([('Scaler', StandardScaler()), ('RFR', RandomForestRegressor())])
ensembles['ScaledETR']=Pipeline([('Scaler', StandardScaler()), ('ETR', ExtraTreesRegressor())])
ensembles['ScaledGBR']=Pipeline([('Scaler', StandardScaler()), ('GBR', GradientBoostingRegressor())])

results=[]

for key in ensembles:
    kfold=KFold(n_splits=num_folds, random_state=seed)
    cv_result=cross_val_score(ensembles[key], X_train, Y_train, cv=kfold, scoring=scoring)
    results.append(cv_result)
    print('%s: %f (%f)' % (key, cv_result.mean(), cv_result.std()))

eval_models()

"""执行结果如图所示，随机梯度上升算法和极端随机树算法具有较高的中位值和分布状况。"""

"""集成算法调参

集成算法都有一个参数n_estimators，这是一个很好的可以用来调整的参数。对于集成参数来说，n_estimators会带来更准确的结果，当然这也有一定的限度。
下面对随机梯度上升(GBM)和极端随机树(ET)算法进行调参，再次比较这两个算法模型的准确度，来确定最终的算法模型"""

#tuning GBM
scaler = StandardScaler().fit(X_train)
rescaledX=scaler.transform(X_train)
param_grid={'n_estimators':[10,50,100,200,300,400,500,600,700,800,900]}
model=GradientBoostingRegressor()
kfold=KFold(n_splits=num_folds, random_state=seed)
grid=GridSearchCV(estimator=model, param_grid=param_grid, scoring=scoring, cv=kfold)
grid_result=grid.fit(X=rescaledX, y=Y_train)

print('Best: %s use %s' % (grid_result.best_score_, grid_result.best_params_))
cv_results=zip(grid_result.cv_results_['mean_test_score'], grid_result.cv_results_['std_test_score'], grid_result.cv_results_['params'])
for mean, std, param in cv_results:
    print('%f (%f) with %r' % (mean, std, param))

#Tuning ET
scaler = StandardScaler().fit(X_train)
rescaledX=scaler.transform(X_train)
param_grid={'n_estimators':[5,10,20,30,40,50,60,70,80,90,100]}
model=ExtraTreesRegressor()
kfold=KFold(n_splits=num_folds, random_state=seed)
grid=GridSearchCV(estimator=model, param_grid=param_grid, scoring=scoring, cv=kfold)
grid_result=grid.fit(X=rescaledX, y=Y_train)

print('Best: %s use %s' % (grid_result.best_score_, grid_result.best_params_))
cv_results=zip(grid_result.cv_results_['mean_test_score'], grid_result.cv_results_['std_test_score'], grid_result.cv_results_['params'])
for mean, std, param in cv_results:
    print('%f (%f) with %r' % (mean, std, param))

"""对于随机梯度上升(GBM)算法来说，最优的n_estimators是500;对于极端随机树(ET)算法来说，最优的n_estimators是90。"""

"""确定最终模型

我们已经确定了使用极端随机树(ET)算法来生成模型，下面就对该算法进行训练和生成模型，并计算模型的准确度"""

#train the ET model
scaler = StandardScaler().fit(X_train)
rescaledX=scaler.transform(X_train)
gbr=ExtraTreesRegressor(n_estimators=90)
gbr.fit(X=rescaledX, y=Y_train)

#evaluate the precision
rescaledX_validation=scaler.transform(X_validation)
predictions=gbr.predict(rescaledX_validation)
print(mean_squared_error(Y_validation, predictions))

from sklearn.model_selection import cross_val_score

cv_scores = cross_val_score(gbr, X_train, Y_train, cv=10)
cv_scores.mean()




