# -*- coding: utf-8 -*-
"""news-classification-preo.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1d4rW-nXEk2Y4_Fs7xFc3hm84heallNOZ
"""

# 참고 : https://github.com/SKT-AI/KoGPT2
!pip install --upgrade mxnet>=1.6.0
!pip install gluonnlp
!pip install transformers
!pip install sentencepiece
!pip install wget

import gluonnlp as nlp
from gluonnlp.data import SentencepieceTokenizer, SentencepieceDetokenizer
from transformers import TFGPT2LMHeadModel
import tensorflow as tf

import pandas as pd
import numpy as np
from tensorflow.keras.layers import Dense, Input, Concatenate
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from sklearn.model_selection import train_test_split
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.callbacks import ModelCheckpoint
import re
import os
from tqdm import tqdm
import matplotlib.pyplot as plt

import wget
import zipfile

# gpt pre-trained model download

# wget.download('https://github.com/NLP-kr/tensorflow-ml-nlp-tf2/releases/download/v1.0/gpt_ckpt.zip')

# with zipfile.ZipFile('gpt_ckpt.zip') as z:
#     z.extractall()

MODEL_PATH = '../input/test-datamodel/gpt_ckpt'
TOKENIZER_PATH = '../input/test-datamodel/gpt_ckpt/gpt2_kor_tokenizer.spiece'

# data load

DATA_PATH = '../input/news-classifiy-final/'
df = pd.read_csv(DATA_PATH + 'train_0412_02.csv', header=0)
df.drop('Unnamed: 0', axis = 1, inplace = True)
df = df.dropna()
df.head()

!mkdir "./gpt2"

# Weight save
ckpt_path = './gpt2/GPT_model_weights_preO.h5'

# Down sampling
topic_count = df.groupby(['topic_idx']).count()
df_sample = pd.DataFrame([np.nan], columns =['title'] )
df_sample['topic_idx'] = np.nan

for i in set(df['topic_idx']):
    df_sample = pd.concat([df_sample, df[df['topic_idx']==i].sample(topic_count.min().iloc[0])])

df_sample = df_sample.dropna()
df_sample['topic_idx'] = df_sample['topic_idx'].astype('int')

# title label split

x = list(df['title'])
y = list(df['topic_idx'])

# Train data slpit

x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.4, random_state = 1, stratify = y)

# Test evaluation data split

x_test, x_eval, y_test, y_eval = train_test_split(x_test, y_test,  test_size=0.5, random_state = 1, stratify = y_test)

# Tokenizer setting

tokenizer = SentencepieceTokenizer(TOKENIZER_PATH, num_best=0, alpha=0)
detokenizer = SentencepieceDetokenizer(TOKENIZER_PATH)
vocab = nlp.vocab.BERTVocab.from_sentencepiece(TOKENIZER_PATH,
                                               mask_token = None,
                                               sep_token = None,
                                               cls_token = None,
                                               unknown_token = '<unk>',
                                               padding_token = '<pad>',
                                               bos_token = '<s>',
                                               eos_token = '</s>')

# data build methods

MAX_LEN = 40

def build_data(x_data, y_label):
    data_sents = []
    data_labels = []

    for sent, label in zip(x_data, y_label):
        tokenized_text = vocab[tokenizer(sent)] # sent = 리뷰한개

        tokens = [vocab[vocab.bos_token]]   # 시작 = <s>
        tokens += pad_sequences([tokenized_text], 
                                MAX_LEN, 
                                value=vocab[vocab.padding_token], 
                                padding='post').tolist()[0] 
        tokens += [vocab[vocab.eos_token]]  # 끝 = </s>

        data_sents.append(tokens)
        data_labels.append(label)

    return np.array(data_sents, dtype=np.int64), np.array(data_labels, dtype=np.int64).reshape(-1, 1)

# data build

x_train, y_train = build_data(x_train, y_train)
x_eval, y_eval = build_data(x_eval, y_eval)
x_test, y_test = build_data(x_test, y_test)

x_train.shape, y_train.shape, x_test.shape, y_test.shape, x_eval.shape, y_eval.shape

# Creat Diction

word2idx = {k:v for k, v in vocab.token_to_idx.items()}
idx2word = {v:k for k, v in word2idx.items()}
idx2word[5000]

# GPT model

gpt_model = TFGPT2LMHeadModel.from_pretrained(MODEL_PATH)
gpt_model.summary()

# gpt model train

gpt_model.trainable = True
gpt_model.summary()

# gpt input

x_input = Input(batch_shape = (None, MAX_LEN + 2), dtype = tf.int32)  # <s>와 </s> 2개 포함

# gpt output

output_gpt = gpt_model(x_input)[0][:, -1, :]

# Downstream task

y_output = Dense(7, activation = 'softmax')(output_gpt)

model = Model(x_input, y_output)
model.compile(loss = 'sparse_categorical_crossentropy', optimizer = Adam(learning_rate = 0.0001))
model.summary()

if os.path.exists(ckpt_path):
    model.load_weights(ckpt_path)
    print('학습된 weight가 적용됐습니다.')

# call back setting

cp_callback = ModelCheckpoint(filepath=ckpt_path, 
                              save_weights_only=True, 
                              verbose=1,
                              save_freq='epoch')

# model fitting

hist = model.fit(x_train, y_train, 
                 validation_data = (x_eval, y_eval), 
                 epochs=3, 
                 batch_size=32,
                 callbacks=[cp_callback])

# Loss history

plt.plot(hist.history['loss'], label='Train loss')
plt.plot(hist.history['val_loss'], label = 'val_loss')
plt.legend()
plt.title("Loss history")
plt.xlabel("epoch")
plt.ylabel("loss")
plt.show()

# test

y_prob = model.predict(x_test)

y_pred = np.argmax(y_prob,axis=1).reshape(-1,1)

Acc = (y_test == y_pred).mean()

print("정확도 = {:.2f}".format(Acc))

