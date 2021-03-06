from __future__ import print_function, division, absolute_import

from odin import backend as K, nnet as N
import tensorflow as tf


@N.Lambda
def test(X, y):
  nb_classes = y.shape.as_list()[-1]
  f = N.Sequence([
      N.Flatten(outdim=2),
      N.Dense(512, activation=K.relu),
      N.Dropout(level=0.5),
      N.Dense(nb_classes, activation=K.linear)
  ], debug=2)
  logit = f(X)
  prob = tf.nn.softmax(logit)
  return {'logit': logit, 'prob': prob}


@N.Lambda
def cnn(X, y):
  nb_classes = y.shape.as_list()[-1]
  with N.args_scope(['Conv', dict(b_init=None, activation=K.linear)],
                    ['BatchNorm', dict(activation=K.relu)]):
    f = N.Sequence([
        N.Dimshuffle(pattern=(0, 2, 3, 1)),
        N.Conv(32, (3, 3), pad='same', stride=(1, 1)),
        N.BatchNorm(),
        N.Conv(32, (3, 3), pad='same', stride=(1, 1),
               b_init=0, activation=K.relu),
        N.Pool(pool_size=(2, 2), strides=None, mode='max'),
        N.Dropout(level=0.25),
        #
        N.Conv(64, (3, 3), pad='same', stride=(1, 1)),
        N.BatchNorm(),
        N.Conv(64, (3, 3), pad='same', stride=(1, 1),
               b_init=0., activation=K.relu),
        N.Pool(pool_size=(2, 2), strides=None, mode='max'),
        N.Dropout(level=0.25),
        #
        N.Flatten(outdim=2),
        N.Dense(512, activation=K.relu),
        N.Dropout(level=0.5),
        N.Dense(nb_classes, activation=K.linear)
    ], debug=1)
  logit = f(X)
  prob = tf.nn.softmax(logit)
  return {'logit': logit, 'prob': prob}
