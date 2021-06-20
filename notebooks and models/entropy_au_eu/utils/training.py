import os
import sys
import math
import string
import random
import shutil

import torch
import torch.nn as nn
import torchvision.transforms as transforms
from torchvision.utils import save_image
from torch.autograd import Variable
import torch.nn.functional as F

from . import imgs as img_utils

from sklearn.metrics import roc_auc_score
from sklearn.metrics import average_precision_score
import numpy as np

#RESULTS_PATH = '.results/'
#WEIGHTS_PATH = '.weights/'
#RESULTS_PATH_67 = '/content/drive/MyDrive/pytorch_tiramisu/results67'
#WEIGHTS_PATH_67 = '/content/drive/MyDrive/pytorch_tiramisu/weights67'
#RESULTS_PATH_103 = '/content/drive/MyDrive/pytorch_tiramisu/results67'
#WEIGHTS_PATH_103 = '/content/drive/MyDrive/pytorch_tiramisu/weights67'


def save_weights(model, epoch, loss, err, WEIGHTS_PATH):
    weights_fname = 'weights-%d-%.3f-%.3f.pth' % (epoch, loss, err)
    weights_fpath = os.path.join(WEIGHTS_PATH, weights_fname)
    torch.save({
            'startEpoch': epoch,
            'loss':loss,
            'error': err,
            'state_dict': model.state_dict()
        }, weights_fpath)
    shutil.copyfile(weights_fpath, WEIGHTS_PATH+'latest.th')

def load_weights(model, fpath):
    print("loading weights '{}'".format(fpath))
    weights = torch.load(fpath)
    startEpoch = weights['startEpoch']
    model.load_state_dict(weights['state_dict'])
    print("loaded weights (lastEpoch {}, loss {}, error {})"
        .format(startEpoch, weights['loss'], weights['error']))
    return startEpoch

def get_predictions(output_batch):
    bs,c,h,w = output_batch.size()
    tensor = output_batch.data
    values, indices = tensor.cpu().max(1)
    indices = indices.view(bs,h,w)
    return indices

def error(preds, targets):
    assert preds.size() == targets.size()
    bs,h,w = preds.size()
    n_pixels = bs*h*w
    incorrect = preds.ne(targets).cpu().sum()
    err = incorrect/n_pixels
    return err

def train(model, trn_loader, optimizer, criterion, epoch):
    model.train()
    trn_loss = 0
    trn_error = 0
    for idx, data in enumerate(trn_loader):
        inputs = Variable(data[0].cuda())
        targets = Variable(data[1].cuda())

        optimizer.zero_grad()
        output = model(inputs)
        loss = criterion(output, targets)
        loss.backward()
        optimizer.step()

        trn_loss += loss.item()
        pred = get_predictions(output)
        trn_error += error(pred, targets.data.cpu())

    trn_loss /= len(trn_loader)
    trn_error /= len(trn_loader)
    return trn_loss, trn_error

def test(model, test_loader, criterion, epoch=1):
    model.eval()
    test_loss = 0
    test_error = 0
    # put the for loop in the with block
    with torch.no_grad():    
        for data, target, _ in test_loader:
            data = data.to(torch.device("cuda"))
            target = target.to(torch.device("cuda"))
            output = model(data)
            test_loss += criterion(output, target).item()
            pred = get_predictions(output)
            test_error += error(pred, target.data.cpu())
    test_loss /= len(test_loader)
    test_error /= len(test_loader)
    return test_loss, test_error

def adjust_learning_rate(lr, decay, optimizer, cur_epoch, n_epochs):
    """Sets the learning rate to the initially
        configured `lr` decayed by `decay` every `n_epochs`"""
    new_lr = lr * (decay ** (cur_epoch // n_epochs))
    for param_group in optimizer.param_groups:
        param_group['lr'] = new_lr

def weights_init(m):
    if isinstance(m, nn.Conv2d):
        nn.init.kaiming_uniform_(m.weight)
        m.bias.data.zero_()

def predict(model, input_loader, n_batches=1):
    input_loader.batch_size = 1
    predictions = []
    model.eval()
    for input, target in input_loader:
        data = Variable(input.cuda(), volatile=True)
        label = Variable(target.cuda())
        output = model(data)
        pred = get_predictions(output)
        predictions.append([input,target,pred])
    return predictions

def view_sample_predictions(model, loader, n):
    inputs, targets = next(iter(loader))
    print(inputs.shape)
    data = inputs.to(torch.device("cuda"))
    label = targets.to(torch.device("cuda"))
    output = model(data)
    pred = get_predictions(output)
    batch_size = inputs.size(0)
    for i in range(min(n, batch_size)):        
        print("MODEL'S PREDICTION")
        img_utils.view_annotated(pred[i])
        print("GROUND TRUTH")
        img_utils.view_annotated(targets[i])
        print("ORIGINAL IMAGE")
        img_utils.view_image(inputs[i])
