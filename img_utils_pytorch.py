#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""
Image deformation using moving least squares.

    * Affine deformation
    * Similarity deformation
    * Rigid deformation

For more details please refer to the Chinese documentation:

    ./doc/Image Deformation.pdf

or the original paper:

    Image deformation using moving least squares
    Schaefer, Mcphail, Warren.

Note:
    In the original paper, the author missed the weight w_j in formular (5).
    In addition, all the formulars in section 2.1 miss the w_j.
    And I have corrected this point in my documentation.

@author: Jian-Wei ZHANG
@email: zjw.cs@zju.edu.cn
@date: 2022/01/12: PyTorch implementation
"""

import torch


device = torch.device("cuda:0" if torch.cuda.is_available() else 'cpu')


def mls_deformation(vy, vx, p, q, alpha=1.0, eps=1e-8, solver=None):
    """ Deformation

    Parameters
    ----------
    vy, vx: ndarray
        coordinate grid, generated by np.meshgrid(gridX, gridY)
    p: ndarray
        an array with size [n, 2], original control points, in (y, x) formats
    q: ndarray
        an array with size [n, 2], final control points, in (y, x) formats
    alpha: float
        parameter used by weights
    eps: float
        epsilon

    Return
    ------
        A deformed image.
    """
    # Exchange p and q and hence we transform destination pixels to the corresponding source pixels.
    p, q = q, p

    grow = vx.shape[0]  # grid rows
    gcol = vy.shape[1]  # grid cols
    ctrls = p.shape[0]  # control points

    # Precompute
    _p = torch.view_as_complex(p)
    _p = _p.reshape(1, 1, ctrls)
    vx = vx.reshape(grow, -1, 1)
    vy = vy.reshape(-1, gcol, 1)
    _v = torch.complex(vx, vy)

    w = 1 / (torch.abs(_p - _v) ** 2 + eps) ** alpha
    w /= torch.sum(w, axis=2, keepdims=True)

    _pstar = torch.sum(w * _p, axis=2, keepdims=True)

    # Calculate q
    _q = torch.view_as_complex(q)
    _q = _q.reshape(1, 1, ctrls)
    _qstar = torch.sum(w * _q, axis=2, keepdims=True)

    # Get final image transfomer -- 3-D array
    _transformers = solver(w, _q, _qstar, _p, _pstar, _v)
    transformers = torch.view_as_real(_transformers)    # 进化回实数域？

    # Removed the points outside the border
    torch.clamp(transformers, torch.Tensor([0]).to(device), torch.Tensor([grow - 1, gcol - 1]).to(device), out=transformers)

    transformers = transformers.reshape(grow, gcol, 2)

    return transformers.long()


def affine_solver(w, _q, _qstar, _p, _pstar, _v):
    grow, gcol = w.shape[:2]
    w = w.reshape(grow, gcol, -1, 1, 1)
    v = torch.view_as_real(_v).reshape(grow, gcol, 1, 1, 2)
    q = torch.view_as_real(_q).reshape(1, 1, -1, 1, 2)
    qstar = torch.view_as_real(_qstar).reshape(grow, gcol, 1, 1, 2)
    p = torch.view_as_real(_p).reshape(1, 1, -1, 1, 2)
    pstar = torch.view_as_real(_pstar).reshape(grow, gcol, 1, 1, 2)
    phat = p - pstar
    phatT = phat.reshape(grow, gcol, -1, 2, 1)
    pTwp = torch.sum(phatT * w * phat, axis=2, keepdims=True)
    pTwq = torch.sum(phatT * w * (q - qstar), axis=2, keepdims=True)
    M = torch.linalg.inv(pTwp) @ pTwq                               # [grow, gcol, 1, 2, 2]
    return torch.view_as_complex((v - pstar) @ M + qstar)


def similarity_solver(w, _q, _qstar, _p, _pstar, _v):
    _M = torch.sum(torch.conj(_p - _pstar) * w * (_q - _qstar), axis=2, keepdims=True)
    mu = torch.sum(w * torch.abs(_p - _pstar) ** 2, axis=2, keepdims=True)
    return (_v - _pstar) * (_M / mu) + _qstar


def rigid_solver(w, _q, _qstar, _p, _pstar, _v):
    _M = torch.sum(torch.conj(_p - _pstar) * w * (_q - _qstar), axis=2, keepdims=True)
    return (_v - _pstar) * (_M / torch.abs(_M)) + _qstar


def mls_affine_deformation(vy, vx, p, q, alpha=1.0, eps=1e-8):
    return mls_deformation(vy, vx, p, q, alpha=alpha, eps=eps, solver=affine_solver)


def mls_similarity_deformation(vy, vx, p, q, alpha=1.0, eps=1e-8):
    return mls_deformation(vy, vx, p, q, alpha=alpha, eps=eps, solver=similarity_solver)


def mls_rigid_deformation(vy, vx, p, q, alpha=1.0, eps=1e-8):
    return mls_deformation(vy, vx, p, q, alpha=alpha, eps=eps, solver=rigid_solver)
