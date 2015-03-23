from __future__ import division

import math
import numpy as np


def labDelta(x, y):
    dL = y.l - x.l
    dA = y.a - x.a
    dB = y.b - x.b
    return math.sqrt(dL**2 + dA**2 + dB**2)


def rgbLabDelta(x, y):
    labX = rgb2lab(x)
    labY = rgb2lab(y)
    return labDelta(labX, labY)


def rgb2xyz(rgb):
    var_R = rgb[:, 0] / 255  # R from 0 to 255
    var_G = rgb[:, 1] / 255  # G from 0 to 255
    var_B = rgb[:, 2] / 255  # B from 0 to 255

    idx = var_R > 0.04045
    var_R[idx] = ((var_R[idx] + 0.055) / 1.055) ** 2.4
    idx = np.logical_not(idx)
    var_R[idx] = var_R[idx] / 12.92

    idx = var_G > 0.04045
    var_G[idx] = ((var_G[idx] + 0.055) / 1.055) ** 2.4
    idx = np.logical_not(idx)
    var_G[idx] = var_G[idx] / 12.92

    idx = var_B > 0.04045
    var_B[idx] = ((var_B[idx] + 0.055) / 1.055) ** 2.4
    idx = np.logical_not(idx)
    var_B[idx] = var_B[idx] / 12.92

    var_R = var_R * 100
    var_G = var_G * 100
    var_B = var_B * 100

    #Observer. = Illuminant = D65
    X = var_R * 0.4124 + var_G * 0.3576 + var_B * 0.1805
    Y = var_R * 0.2126 + var_G * 0.7152 + var_B * 0.0722
    Z = var_R * 0.0193 + var_G * 0.1192 + var_B * 0.9505
    #xyz = XYZColor(X,Y,Z)

    return np.c_[X, Y, Z]


def xyz2lab(xyz):
    ref_X = 095.047
    ref_Y = 100.000
    ref_Z = 108.883
    var_X = xyz[:, 0] / ref_X
    var_Y = xyz[:, 1] / ref_Y
    var_Z = xyz[:, 2] / ref_Z

    idx = var_X > 0.008856
    var_X[idx] = var_X[idx] ** (1/3)
    idx = np.logical_not(idx)
    var_X[idx] = (7.787 * var_X[idx]) + (16 / 116)

    idx = var_Y > 0.008856
    var_Y[idx] = var_Y[idx] ** (1/3)
    idx = np.logical_not(idx)
    var_Y[idx] = (7.787 * var_Y[idx]) + (16 / 116)

    idx = var_Z > 0.008856
    var_Z[idx] = var_Z[idx] ** (1/3)
    idx = np.logical_not(idx)
    var_Z[idx] = (7.787 * var_Z[idx]) + (16 / 116)

    L = (116 * var_Y) - 16
    A = 500 * (var_X - var_Y)
    B = 200 * (var_Y - var_Z)
    #lab = LabColor(L,A,B)

    return np.c_[L, A, B]


def lab2xyz(lab):
    var_Y = (lab.l + 16) / 116
    var_X = lab.a / 500 + var_Y
    var_Z = var_Y - lab.b / 200

    if ( var_Y**3 > 0.008856 ): var_Y = var_Y**3
    else:                       var_Y = ( var_Y - 16 / 116 ) / 7.787
    if ( var_X**3 > 0.008856 ): var_X = var_X**3
    else:                       var_X = ( var_X - 16 / 116 ) / 7.787
    if ( var_Z**3 > 0.008856 ): var_Z = var_Z**3
    else:                       var_Z = ( var_Z - 16 / 116 ) / 7.787

    ref_X = 095.047
    ref_Y = 100.000
    ref_Z = 108.883
    X = ref_X * var_X
    Y = ref_Y * var_Y
    Z = ref_Z * var_Z
    xyz = XYZColor(X, Y, Z)

    return xyz


def xyz2rgb(xyz):
    var_X = xyz.x / 100  # X from 0 to  95.047
    var_Y = xyz.y / 100  # Y from 0 to 100.000
    var_Z = xyz.z / 100  # Z from 0 to 108.883

    var_R = var_X *  3.2406 + var_Y * -1.5372 + var_Z * -0.4986
    var_G = var_X * -0.9689 + var_Y *  1.8758 + var_Z *  0.0415
    var_B = var_X *  0.0557 + var_Y * -0.2040 + var_Z *  1.0570

    if ( var_R > 0.0031308 ): var_R = 1.055 * ( var_R ** ( 1 / 2.4 ) ) - 0.055
    else:                     var_R = 12.92 * var_R
    if ( var_G > 0.0031308 ): var_G = 1.055 * ( var_G ** ( 1 / 2.4 ) ) - 0.055
    else:                     var_G = 12.92 * var_G
    if ( var_B > 0.0031308 ): var_B = 1.055 * ( var_B ** ( 1 / 2.4 ) ) - 0.055
    else:                     var_B = 12.92 * var_B

    R = var_R * 255
    G = var_G * 255
    B = var_B * 255
    rgb = RGBColor(R, G, B)

    return rgb


def rgb2lab(rgb):
    tmp = rgb2xyz(rgb)
    return xyz2lab(tmp)


def lab2rgb(lab):
    tmp = lab2xyz(lab)
    return xyz2rgb(tmp)


class LabColor:
    def __init__(self, l, a, b):
        self.l = l
        self.a = a
        self.b = b


class RGBColor:
    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b


class XYZColor:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z