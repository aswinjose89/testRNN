import keras
from keras.datasets import imdb 
from keras.layers import *
from keras import *
from keras.models import *
import copy
import keras.backend as K
import numpy as np
from keras.preprocessing import sequence 
from utils import getActivationValue,layerName, hard_sigmoid
from keract import get_activations_single_layer

class Sentiment:
    def __init__(self):
        self.X_train = None
        self.y_train = None
        self.X_test = None
        self.y_test = None
        self.model = None
        
        self.top_words = 50000
        self.word_to_id = keras.datasets.imdb.get_word_index()
        self.INDEX_FROM=3
        self.max_review_length = 500
        self.embedding_vector_length = 32 
        
        self.word_to_id = {k:(v+self.INDEX_FROM) for k,v in self.word_to_id.items()}
        self.word_to_id["<PAD>"] = 0
        self.word_to_id["<START>"] = 1
        self.word_to_id["<UNK>"] = 2
        self.id_to_word = {value:key for key,value in self.word_to_id.items()}

        self.numAdv = 0
        self.numSamples = 0
        self.perturbations = []
        
        self.load_data()
        self.pre_processing_X()

    def load_data(self): 
        (self.X_train, self.y_train), (self.X_test, self.y_test) = imdb.load_data(num_words=self.top_words)
        
    def load_model(self):
        self.model=load_model('models/sentiment-lstm.h5')
        self.model.compile(loss='binary_crossentropy',optimizer='adam', metrics=['accuracy']) 
        self.model.summary()
        
    def layerName(self,layer):
        layerNames = [layer.name for layer in self.model.layers]
        return layerNames[layer]
        
    def train_model(self):
        self.load_data()
        self.pre_processing_X()
        self.model = Sequential() 
        self.model.add(Embedding(self.top_words, self.embedding_vector_length, input_length=self.max_review_length, input_shape=(self.top_words,))) 
        self.model.add(LSTM(100))
        self.model.add(Dense(1, activation='sigmoid')) 
        self.model.compile(loss='binary_crossentropy',optimizer='adam', metrics=['accuracy']) 
        print(self.model.summary()) 
        self.model.fit(self.X_train, self.y_train, validation_data=(self.X_test, self.y_test), nb_epoch=10, batch_size=64) 
        scores = self.model.evaluate(self.X_test, self.y_test, verbose=0)
        print("Accuracy: %.2f%%" % (scores[1]*100))
        self.model.save('models/sentiment-lstm.h5')

    def getOutputResult(self,model,test):
        functors = self.getFunctors(model)
        return functors[-1]([test, 1.])[0][0]

    def displayInfo(self,test):
        model = self.model
        text = self.fromIDToText(test)
        print("review content: %s"%(text))
        conf = get_activations_single_layer(model,np.array([test]),self.layerName(-1))
        print("current confidence: %.2f\n"%(conf))
        if conf >= 0.5 : 
            return (1,conf)
        else: 
            return (-1,1-conf)

    def pre_processing_X(self): 
        self.X_train = sequence.pad_sequences(self.X_train, maxlen=self.max_review_length) 
        self.X_test = sequence.pad_sequences(self.X_test, maxlen=self.max_review_length) 
        
    def pre_processing_x(self,tmp):
        tmp_padded = sequence.pad_sequences([tmp], maxlen=self.max_review_length) 
        #print("%s. Sentiment: %s" % (review,model.predict(np.array([tmp_padded][0]))[0][0]))
        test = np.array([tmp_padded][0])
        #print("input shape: %s"%(str(test.shape)))
        return test
        
    def validateID(self,ids):
        flag = False 
        ids2 = []
        for id in ids: 
            if not (id  in self.id_to_word.keys()): 
                ids2.append(min(self.id_to_word.keys(), key=lambda x:abs(x-id)))
                flag = True
            else: 
                ids2.append(id)
        if flag == True: 
            return validateID(ids2)
        else: return ids

    def displayIDRange(self):
        minID = min(self.word_to_id.values())+self.INDEX_FROM
        maxID = max(self.word_to_id.values())+self.INDEX_FROM
        print("ID range: %s--%s"%(minID,maxID))
        
    def fromTextToID(self,review): 
        tmp = []
        for word in review.split(" "):
            if word in self.word_to_id:
                if self.word_to_id[word] <= self.top_words :
                    tmp.append(self.word_to_id[word])
        return tmp
    
    def fromIDToText(self,ids): 
        tmp = ""
        for id in ids:
            if id > 2: 
                tmp += self.id_to_word[id] + " "
        return tmp.strip()

    def updateSample(self,label2,label1,m,o):
        if label2 != label1 and o == True:
            self.numAdv += 1
            self.perturbations.append(m)
        self.numSamples += 1
        self.displaySuccessRate()

    def displaySamples(self):
        print("%s samples are considered" % (self.numSamples))

    def displaySuccessRate(self):
        print("%s samples, within which there are %s adversarial examples" % (self.numSamples, self.numAdv))
        print("the rate of adversarial examples is %.2f\n" % (self.numAdv / self.numSamples))

    def displayPerturbations(self):
        if self.numAdv > 0:
            print("the average perturbation of the adversarial examples is %s" % (sum(self.perturbations) / self.numAdv))
            print("the smallest perturbation of the adversarial examples is %s" % (min(self.perturbations)))

    # calculate the lstm hidden state and cell state manually (no dropout)
    def cal_hidden_state(self, test):
        acx = get_activations_single_layer(self.model, np.array([test]), self.layerName(0))
        units = int(int(self.model.layers[1].trainable_weights[0].shape[1]) / 4)
        # print("No units: ", units)
        # lstm_layer = model.layers[1]
        W = self.model.layers[1].get_weights()[0]
        U = self.model.layers[1].get_weights()[1]
        b = self.model.layers[1].get_weights()[2]

        W_i = W[:, :units]
        W_f = W[:, units: units * 2]
        W_c = W[:, units * 2: units * 3]
        W_o = W[:, units * 3:]

        U_i = U[:, :units]
        U_f = U[:, units: units * 2]
        U_c = U[:, units * 2: units * 3]
        U_o = U[:, units * 3:]

        b_i = b[:units]
        b_f = b[units: units * 2]
        b_c = b[units * 2: units * 3]
        b_o = b[units * 3:]

        # calculate the hidden state value
        h_t = np.zeros((self.max_review_length, units))
        c_t = np.zeros((self.max_review_length, units))
        f_t = np.zeros((self.max_review_length, units))
        h_t0 = np.zeros((1, units))
        c_t0 = np.zeros((1, units))

        for i in range(0, self.max_review_length):
            f_gate = hard_sigmoid(np.dot(acx[i, :], W_f) + np.dot(h_t0, U_f) + b_f)
            i_gate = hard_sigmoid(np.dot(acx[i, :], W_i) + np.dot(h_t0, U_i) + b_i)
            o_gate = hard_sigmoid(np.dot(acx[i, :], W_o) + np.dot(h_t0, U_o) + b_o)
            new_C = np.tanh(np.dot(acx[i, :], W_c) + np.dot(h_t0, U_c) + b_c)
            c_t0 = f_gate * c_t0 + i_gate * new_C
            h_t0 = o_gate * np.tanh(c_t0)
            c_t[i, :] = c_t0
            h_t[i, :] = h_t0
            f_t[i, :] = f_gate

        return h_t, c_t, f_t



