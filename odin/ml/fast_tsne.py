from __future__ import absolute_import, division, print_function

import warnings

import numpy as np

from odin.utils.crypto import md5_checksum
from odin.utils.mpi import MPI, cpu_count

_cached_values = {}


# ===========================================================================
# auto-select best TSNE
# ===========================================================================
def _create_key(framework, kwargs, md5):
  key = dict(kwargs)
  del key['verbose']
  key['md5'] = md5
  return framework + str(list(sorted(key.items(), key=lambda x: x[0])))


def fast_tsne(*X,
              n_components=2,
              n_samples=None,
              perplexity=30.0,
              early_exaggeration=8.0,
              learning_rate=200.0,
              n_iter=1000,
              n_iter_without_progress=300,
              min_grad_norm=1e-7,
              metric="euclidean",
              init="random",
              verbose=0,
              random_state=1234,
              method='barnes_hut',
              angle=0.5,
              n_jobs=4,
              combined=True,
              return_model=False,
              force_sklearn=False):
  r"""
  Arguments:
    n_components : int, optional (default: 2)
        Dimension of the embedded space.
    n_samples : {int, None}
        if given, downsampling the data to given number of sample
    perplexity : float, optional (default: 30)
        The perplexity is related to the number of nearest neighbors that
        is used in other manifold learning algorithms. Larger datasets
        usually require a larger perplexity. Consider selecting a value
        between 5 and 50. The choice is not extremely critical since t-SNE
        is quite insensitive to this parameter.
    early_exaggeration : float, optional (default: 8.0)
        Controls how tight natural clusters in the original space are in
        the embedded space and how much space will be between them. For
        larger values, the space between natural clusters will be larger
        in the embedded space. Again, the choice of this parameter is not
        very critical. If the cost function increases during initial
        optimization, the early exaggeration factor or the learning rate
        might be too high.
    learning_rate : float, optional (default: 200.0)
        The learning rate for t-SNE is usually in the range [10.0, 1000.0]. If
        the learning rate is too high, the data may look like a 'ball' with any
        point approximately equidistant from its nearest neighbours. If the
        learning rate is too low, most points may look compressed in a dense
        cloud with few outliers. If the cost function gets stuck in a bad local
        minimum increasing the learning rate may help.
    n_iter : int, optional (default: 1000)
        Maximum number of iterations for the optimization. Should be at
        least 250.
    n_iter_without_progress : int, optional (default: 300)
        Maximum number of iterations without progress before we abort the
        optimization, used after 250 initial iterations with early
        exaggeration. Note that progress is only checked every 50 iterations so
        this value is rounded to the next multiple of 50.
    min_grad_norm : float, optional (default: 1e-7)
        If the gradient norm is below this threshold, the optimization will
        be stopped.
    metric : string or callable, optional
        The metric to use when calculating distance between instances in a
        feature array. If metric is a string, it must be one of the options
        allowed by scipy.spatial.distance.pdist for its metric parameter, or
        a metric listed in pairwise.PAIRWISE_DISTANCE_FUNCTIONS.
        If metric is "precomputed", X is assumed to be a distance matrix.
        Alternatively, if metric is a callable function, it is called on each
        pair of instances (rows) and the resulting value recorded. The callable
        should take two arrays from X as input and return a value indicating
        the distance between them. The default is "euclidean" which is
        interpreted as squared euclidean distance.
    init : string or numpy array, optional (default: "random")
        Initialization of embedding. Possible options are 'random', 'pca',
        and a numpy array of shape (n_samples, n_components).
        PCA initialization cannot be used with precomputed distances and is
        usually more globally stable than random initialization.
    verbose : int, optional (default: 0)
        Verbosity level.
    random_state : int, RandomState instance or None, optional (default: None)
        If int, random_state is the seed used by the random number generator;
        If RandomState instance, random_state is the random number generator;
        If None, the random number generator is the RandomState instance used
        by `np.random`.  Note that different initializations might result in
        different local minima of the cost function.
    method : string (default: 'barnes_hut')
        By default the gradient calculation algorithm uses Barnes-Hut
        approximation running in O(NlogN) time. method='exact'
        will run on the slower, but exact, algorithm in O(N^2) time. The
        exact algorithm should be used when nearest-neighbor errors need
        to be better than 3%. However, the exact method cannot scale to
        millions of examples.
    angle : float (default: 0.5)
        Only used if method='barnes_hut'
        This is the trade-off between speed and accuracy for Barnes-Hut T-SNE.
        'angle' is the angular size (referred to as theta in [3]) of a distant
        node as measured from a point. If this size is below 'angle' then it is
        used as a summary node of all points contained within it.
        This method is not very sensitive to changes in this parameter
        in the range of 0.2 - 0.8. Angle less than 0.2 has quickly increasing
        computation time and angle greater 0.8 has quickly increasing error.
    return_model : a Boolean, if `True`, return the trained t-SNE model
    combined : a Boolean, if `True`, combined all arrays into a single array
      for training t-SNE.
  """
  assert len(X) > 0, "No input is given!"
  if isinstance(X[0], (tuple, list)):
    X = X[0]
  if not all(isinstance(x, np.ndarray) for x in X):
    raise ValueError("`X` can only be list of numpy.ndarray or numpy.ndarray")
  # ====== kwarg for creating T-SNE class ====== #
  kwargs = dict(locals())
  del kwargs['X']
  combined = kwargs.pop('combined', combined)
  return_model = kwargs.pop('return_model', return_model)
  n_samples = kwargs.pop('n_samples', n_samples)
  force_sklearn = kwargs.pop('force_sklearn', force_sklearn)
  # ====== downsampling ====== #
  if n_samples is not None:
    n_samples = int(n_samples)
    assert n_samples > 0
    new_X = []
    rand = random_state if isinstance(random_state, np.random.RandomState) else \
    np.random.RandomState(seed=random_state)
    for x in X:
      if x.shape[0] > n_samples:
        ids = rand.permutation(x.shape[0])[:n_samples]
        x = x[ids]
      new_X.append(x)
    X = new_X
  # ====== import proper T-SNE ====== #
  tsne_version = None
  if not force_sklearn:
    try:
      from cuml.manifold import TSNE
      tsne_version = 'cuda'
    except ImportError:
      warnings.warn(
          "Install GPUs-accelerated t-SNE from `https://github.com/rapidsai/cuml` "
          "using `conda install -c rapidsai -c nvidia -c conda-forge -c defaults cuml=0.10 python=3.6 cudatoolkit=10.0`"
      )
      try:
        from MulticoreTSNE import MulticoreTSNE as TSNE
        tsne_version = 'multicore'
      except ImportError:
        warnings.warn(
            "Install MulticoreTSNE from "
            "pip install git+https://github.com/DmitryUlyanov/Multicore-TSNE.git"
            " to accelerate the T-SNE on multiple CPU cores.")
  if tsne_version is None:
    from sklearn.manifold import TSNE
    tsne_version = 'sklearn'
  # ====== modify kwargs ====== #
  if tsne_version == 'cuda':
    del kwargs['n_jobs']
  elif tsne_version == 'multicore':
    pass
  else:
    del kwargs['n_jobs']
  # ====== getting cached values ====== #
  results = []
  X_new = []
  X_size = []
  if combined:
    X_size = [x.shape[0] for x in X]
    x = np.vstack(X) if len(X) > 1 else X[0]
    md5 = md5_checksum(x)
    key = _create_key(tsne_version, kwargs, md5)
    if key in _cached_values:
      results.append((0, _cached_values[key]))
    else:
      X_new.append((0, md5, x))
  else:
    for i, x in enumerate(X):
      md5 = md5_checksum(x)
      key = _create_key(tsne_version, kwargs, md5)
      if key in _cached_values:
        results.append((i, _cached_values[key]))
      else:
        X_new.append((i, md5, x))

  # ====== perform T-SNE ====== #
  def apply_tsne(j):
    idx, md5, x = j
    tsne = TSNE(**kwargs)
    return (idx, md5, tsne.fit_transform(x), tsne if return_model else None)

  # only 1 X, no need for MPI
  if len(X_new) == 1 or tsne_version in ('cuda', 'multicore'):
    for x in X_new:
      idx, md5, x, model = apply_tsne(x)
      results.append((idx, x))
      _cached_values[_create_key(tsne_version, kwargs, md5)] = x
  else:
    mpi = MPI(jobs=X_new,
              func=apply_tsne,
              batch=1,
              ncpu=min(len(X_new),
                       cpu_count() - 1))
    model = []
    for idx, md5, x, m in mpi:
      results.append((idx, x))
      _cached_values[_create_key(tsne_version, kwargs, md5)] = x
      model.append(m)
  # ====== return and clean ====== #
  if combined and len(X_size) > 1:
    indices = [0] + np.cumsum(X_size).tolist()
    results = [results[0][1][s:e] for s, e in zip(indices, indices[1:])]
  else:
    results = sorted(results, key=lambda a: a[0])
    results = [r[1] for r in results]
  results = results[0] if len(results) == 1 else results
  if return_model:
    return results, model
  return results
