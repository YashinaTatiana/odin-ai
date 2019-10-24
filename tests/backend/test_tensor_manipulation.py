from __future__ import absolute_import, division, print_function

import os
import unittest

import numpy as np
import tensorflow as tf
import torch

from odin import backend as bk

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'

tf.random.set_seed(8)
np.random.seed(8)
torch.manual_seed(8)

# ===========================================================================
# Helpers
# ===========================================================================
x = np.random.rand(12, 25, 8).astype('float32')
y = torch.Tensor(x)
z = tf.convert_to_tensor(x)


def _equal(self, info, a: np.ndarray, b: torch.Tensor, c: tf.Tensor):
  assert all(
      int(i) == int(j) == int(k) for i, j, k in zip(a.shape, b.shape, c.shape)),\
        "Input shape: %s, info: %s, output shapes mismatch: %s, %s and %s" % \
          (str(x.shape), str(info), str(a.shape), str(b.shape), str(c.shape))
  self.assertTrue(np.all(
      np.logical_and(np.allclose(a, b.numpy()), np.allclose(a, c.numpy()))),
                  msg="info: %s, output value mismatch, \n%s\n%s\n%s" %
                  (info, str(a), str(b.numpy()), str(c.numpy())))


# ===========================================================================
# test case
# ===========================================================================
class BackendTensorTest(unittest.TestCase):

  def test_reshape(self):

    def reshape_and_test(newshape):
      a = bk.reshape(x, newshape)
      b = bk.reshape(y, newshape)
      c = bk.reshape(z, newshape)
      _equal(self, newshape, a, b, c)

    reshape_and_test((-1, 8))
    reshape_and_test((8, 12, 25))
    reshape_and_test((-1, [1]))
    reshape_and_test(([-1], -1))
    reshape_and_test(([-1], [1], -1))

  def test_transpose(self):

    def transpose_and_test(pattern):
      a = bk.transpose(x, pattern)
      b = bk.transpose(y, pattern)
      c = bk.transpose(z, pattern)
      _equal(self, pattern, a, b, c)

    transpose_and_test((0, 2, 1))
    transpose_and_test((0, 2, 1, 'x'))
    transpose_and_test((1, 0, 'x', 2))
    transpose_and_test((1, 'x', 0, 'x', 2))
    transpose_and_test(('x', 1, 'x', 0, 'x', 2, 'x'))

  def test_flatten(self):

    def flatten_and_test(n):
      a = bk.flatten(x, n)
      b = bk.flatten(y, n)
      c = bk.flatten(z, n)
      _equal(self, n, a, b, c)

    flatten_and_test(1)
    flatten_and_test(2)

  def test_swapaxes(self):

    def swapaxes_and_test(a1, a2):
      a = bk.swapaxes(x, a1, a2)
      b = bk.swapaxes(y, a1, a2)
      c = bk.swapaxes(z, a1, a2)
      _equal(self, (a1, a2), a, b, c)

    swapaxes_and_test(1, 2)
    swapaxes_and_test(0, 2)
    swapaxes_and_test(1, 0)

  def test_stats_and_reduce(self):
    for axis in (1, 2, None):
      for name, fn in (
          ("min_keepdims",
           lambda _: bk.reduce_min(_, axis=axis, keepdims=True)),
          ("min", lambda _: bk.reduce_min(_, axis=axis, keepdims=False)),
          ("max_keepdims",
           lambda _: bk.reduce_max(_, axis=axis, keepdims=True)),
          ("max", lambda _: bk.reduce_max(_, axis=axis, keepdims=False)),
          ("mean_keepdims",
           lambda _: bk.reduce_mean(_, axis=axis, keepdims=True)),
          ("mean", lambda _: bk.reduce_mean(_, axis=axis, keepdims=False)),
          ("var_keepdims",
           lambda _: bk.reduce_var(_, axis=axis, keepdims=True)),
          ("var", lambda _: bk.reduce_var(_, axis=axis, keepdims=False)),
          ("std_keepdims",
           lambda _: bk.reduce_std(_, axis=axis, keepdims=True)),
          ("std", lambda _: bk.reduce_std(_, axis=axis, keepdims=False)),
          ("sum_keepdims",
           lambda _: bk.reduce_sum(_, axis=axis, keepdims=True)),
          ("sum", lambda _: bk.reduce_sum(_, axis=axis, keepdims=False)),
          ("prod_keepdims",
           lambda _: bk.reduce_prod(_, axis=axis, keepdims=True)),
          ("prod", lambda _: bk.reduce_prod(_, axis=axis, keepdims=False)),
          ("all_keepdims",
           lambda _: bk.reduce_all(_, axis=axis, keepdims=True)),
          ("all", lambda _: bk.reduce_all(_, axis=axis, keepdims=False)),
          ("any_keepdims",
           lambda _: bk.reduce_any(_, axis=axis, keepdims=True)),
          ("any", lambda _: bk.reduce_any(_, axis=axis, keepdims=False)),
          ("logsumexp_keepdims",
           lambda _: bk.reduce_logsumexp(_, axis=axis, keepdims=True)),
          ("logsumexp",
           lambda _: bk.reduce_logsumexp(_, axis=axis, keepdims=False)),
      ):
        # some functions are not supported by pytorch
        if any(_ in name
               for _ in ('min', 'max', 'prod', 'all', 'any')) and axis is None:
          continue
        a = fn(x)
        b = fn(y)
        c = fn(z)
        _equal(self, name, a, b, c)

    a1, a2 = bk.moments(x, axis=1)
    b1, b2 = bk.moments(y, axis=1)
    c1, c2 = bk.moments(z, axis=1)
    _equal(self, "moments_mean", a1, b1, c1)
    _equal(self, "moments_var", a2, b2, c2)

  def test_variable_and_gradient(self):
    with bk.framework_('torch'):
      w = bk.variable(x, trainable=True)
      s1 = bk.reduce_sum(w).detach().numpy()
      g1, o1 = bk.grad(lambda: bk.reduce_sum(bk.power(w, 2)),
                       w,
                       return_outputs=True)

    with bk.framework_('tf'):
      w = bk.variable(x, trainable=True)
      s2 = bk.reduce_sum(w).numpy()
      g2, o2 = bk.grad(lambda: bk.reduce_sum(bk.power(w, 2)),
                       w,
                       return_outputs=True)

    self.assertTrue(s1 == s2)
    self.assertTrue(np.all(np.isclose(g1[0].numpy(), g2[0].numpy())))
    self.assertTrue(np.all(np.isclose(o1[0].detach().numpy(), o2[0].numpy())))


if __name__ == '__main__':
  unittest.main()