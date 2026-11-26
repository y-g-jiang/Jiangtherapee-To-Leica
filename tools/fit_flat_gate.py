from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flat_refinement import features


def patches(seed):
    random = np.random.default_rng(seed)
    rows,cols = np.mgrid[-32:32,-32:32].astype(np.float32)
    samples,labels,energies = [],[],[]
    for index in range(480):
        angle = random.uniform(0,np.pi)
        coord = rows*np.sin(angle) + cols*np.cos(angle)
        plane = coord*random.uniform(-.45,.45)
        plane += random.uniform(0,12)*np.sin(coord/random.uniform(25,65))
        background = plane[...,None] + random.uniform(42,205,(1,1,3))
        smooth = index%2 == 0
        if not smooth:
            period = random.uniform(3,14)
            detail = np.sin(coord*(2*np.pi/period) + random.uniform(0,2*np.pi))
            if index%4 == 1:
                detail = np.sign(detail)
            background += detail[...,None]*random.uniform(4,28,(1,1,3))
        noisy = background+random.normal(0,random.uniform(0,2.8),background.shape)
        signal = features(noisy.astype(np.float32))[15:-15:4,15:-15:4].reshape(-1,2)
        stripe = np.cos(2*np.pi*rows/16 + random.uniform(0,2*np.pi))
        stripe += random.uniform(0,1)*np.cos(2*np.pi*cols/16)
        samples.append(signal)
        labels.extend([float(smooth)]*len(signal))
        energies.extend((stripe[15:-15:4,15:-15:4]**2).ravel())
    return np.column_stack([np.ones(len(labels)),np.concatenate(samples)]),np.array(labels),np.array(energies)


def fit():
    inputs,target,energy = patches(73241)
    weights = np.zeros(3)
    for iteration in range(2400):
        logits = np.einsum('ij,j->i',inputs,weights)
        prob = 1/(1+np.exp(-logits))
        error = (prob-target)*(1+2*target)
        error -= 6*energy*target*(1-prob)**2*prob
        gradient = np.einsum('ij,i->j',inputs,error)/len(target)
        weights -= .15*(gradient+.0004*weights)
        weights[1:] = np.minimum(weights[1:],0)
    inputs,target,_ = patches(81937)
    logits = np.einsum('ij,j->i',inputs,weights)
    print('Weights:',tuple(np.round(weights,6)))
    print('Held-out patch sample recall, smooth/texture:',(logits[target==1]>0).mean(),(logits[target==0]<0).mean())


if __name__=='__main__':
    fit()
