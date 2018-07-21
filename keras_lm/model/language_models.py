import os
import numpy as np

os.environ["CUDA_VISIBLE_DEVICES"]="1"
from keras.layers import Input, CuDNNLSTM, LSTM, Embedding, Dense, Reshape, LSTM, TimeDistributed, Dropout, Lambda, Dot, dot, Concatenate
from keras.models import Model
from keras.optimizers import Adam
import keras.backend as K
from keras.constraints import unit_norm

from keras_lm.model.tied_embeddings import TiedEmbeddingsTransposed
from keras_lm.model.qrnn import QRNN


def build_language_model(num_words, dropout=0.1, dropouth=0.3, dropouti=0.2, dropoute=0.1, wdrop=0.5,
                         tie_weights=True, use_qrnn=False, use_gpu=False):

    inp = Input(shape=(None,))
    emb = Embedding(num_words,300)
    emb_inp = emb(inp)
    emb_inp = Dropout(dropouti)(emb_inp)

    if use_qrnn:
        rnn = QRNN(1024, return_sequences=True, window_size=2)(emb_inp)
        rnn = QRNN(1024, return_sequences=True, window_size=1)(rnn)
        rnn = QRNN(300, return_sequences=True,window_size=1)(rnn)
    else:
        RnnUnit = CuDNNLSTM if use_gpu else LSTM
        rnn = RnnUnit(1024, return_sequences=True)(emb_inp)
        rnn = RnnUnit(1024, return_sequences=True)(rnn)
        rnn = RnnUnit(300, return_sequences=True)(rnn)

    if tie_weights:
        logits = TimeDistributed(TiedEmbeddingsTransposed(tied_to=emb, activation='softmax'))(rnn)
    else:
        logits = TimeDistributed(Dense(num_words, activation='softmax'))(rnn)
    out = Dropout(dropout)(logits)
    model = Model(inputs=inp, outputs=out)
    model.compile(optimizer=Adam(lr=3e-4, beta_1=0.8, beta_2=0.99), loss='sparse_categorical_crossentropy')
    return model


def build_many_to_one_language_model(num_words, embedding_size=300, use_gpu=False):
    RnnUnit = CuDNNLSTM if use_gpu else LSTM
    inp = Input(shape=(None,))
    emb = Embedding(num_words, embedding_size)
    emb_inp = emb(inp)
    rnn = RnnUnit(1024, return_sequences=True)(emb_inp)
    rnn = RnnUnit(1024, return_sequences=True)(rnn)
    rnn = RnnUnit(embedding_size)(rnn)
    #rnn = QRNN(256, return_sequences=True)(emb_inp)
    #rnn = QRNN(256)(rnn)
    #den = Dense(SEQ_LEN, activation='relu')(rnn)
    #out = TimeDistributed(Dense(num_words, activation='softmax'))(rnn)
    out = TiedEmbeddingsTransposed(tied_to=emb, activation='softmax')(rnn)
    model = Model(inputs=inp, outputs=out)
    #model = multi_gpu_model(model, gpus=2)
    model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')
    return model


def build_fast_language_model(num_words, embedding_size=300, use_gpu=False):
    """
    Adatped from http://adventuresinmachinelearning.com/word2vec-keras-tutorial/
    :param num_words:
    :param embedding_size:
    :param use_gpu:
    :return:
    """
    # create some input variables
    inp = Input(shape=(None,), name='input')
    inp_target = Input(shape=(None,), name='target')  # this is the shifted sequence

    emb = Embedding(num_words, embedding_size, name='embedding',  embeddings_constraint=unit_norm(axis=1))

    emb_inp = emb(inp)
    emb_target = emb(inp_target)

    RnnUnit = CuDNNLSTM if use_gpu else LSTM
    rnn = RnnUnit(512, return_sequences=True)(emb_inp)
    #rnn = RnnUnit(1024, return_sequences=True)(rnn)
    rnn = RnnUnit(embedding_size, return_sequences=True)(rnn)

    #TODO: cheesy way to perform the timedistributed dot product
    helper_tensor = Concatenate()([rnn, emb_target])
    reshaped = Reshape((-1, embedding_size, 2))(helper_tensor)

    def tensor_product(x):
        a = x[:, :, :, 0]
        b = x[:, :, :, 1]
        y = K.sum(a * b, axis=-1, keepdims=False)
        return y
    similarity = Lambda(tensor_product)(reshaped)  # similarity is between -1 and 1

    model = Model(inputs=[inp, inp_target], outputs=similarity)
    model.compile(loss='mse', optimizer=Adam(lr=3e-4, beta_1=0.8, beta_2=0.99))
    return model


if __name__ == '__main__':
    model = build_language_model(num_words=100)
    model.summary()

    simple_model = build_many_to_one_language_model(num_words=100, embedding_size=300)
    simple_model.summary()

    fast_model = build_fast_language_model(num_words=100, embedding_size=300, use_gpu=False)
    fast_model.summary()