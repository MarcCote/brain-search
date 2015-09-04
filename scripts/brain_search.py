#!/usr/bin/env python
from __future__ import division

import os
from os.path import join as pjoin

import json
import time
import numpy as np
import pylab as plt
import nibabel as nib

from itertools import chain
import brainsearch.vizu as vizu

#from brainsearch.imagespeed import blockify
from brainsearch.brain_database import BrainDatabaseManager
from brainsearch.brain_data import brain_data_factory
from brainsearch.utils import Timer
from brainsearch import framework

from nearpy.distances import EuclideanDistance
from nearpy.filters import NearestFilter

from brainsearch.brain_processing import BrainPipelineProcessing, BrainNormalization, BrainResampling

import argparse

#PORT = 4242
PORT = 6379
OFFSET = 0.01


def build_subcommand_list(subparser):
    DESCRIPTION = "List available brain databases."

    p = subparser.add_parser("list",
                             description=DESCRIPTION,
                             help=DESCRIPTION,
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument('name', type=str, nargs='?', help='name of the brain database')
    p.add_argument('-v', action='store_true', help='display more information about brain databases')
    p.add_argument('-f', action='store_true', help='check integrity of brain databases')


def build_subcommand_clear(subparser):
    DESCRIPTION = "Clear brain databases."

    p = subparser.add_parser("clear",
                             description=DESCRIPTION,
                             help=DESCRIPTION,
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument('names', metavar="name", type=str, nargs="*", help='name of the brain database to delete')
    p.add_argument('-f', action='store_true', help='clear also metadata')


def build_subcommand_init(subparser):
    DESCRIPTION = "Build a new brain database (nearpy's engine)."

    p = subparser.add_parser("init",
                             description=DESCRIPTION,
                             help=DESCRIPTION)

    p.add_argument('name', type=str, help='name of the brain database')
    p.add_argument('shape', metavar="X,Y,...", type=str, help="data's shape or patch shape")
    p.add_argument('--LSH', metavar="N", type=int, help='numbers of random projections')
    p.add_argument('--LSH_PCA', metavar="N", type=int, help='numbers of random projections in PCA space')
    p.add_argument('--PCA', metavar="K", type=int, help='use K eigenvectors')
    p.add_argument('--SH', metavar="K", type=int, help='length of hash codes generated by Spectral Hashing')
    p.add_argument('--trainset', type=str, help='JSON file use to "train" PCA')
    p.add_argument('--pca_pkl', type=str, help='pickle file containing the PCA information of the data')
    p.add_argument('--bounds_pkl', type=str, help='pickle file containing the bounds used by spectral hashing')


def build_subcommand_add(subparser):
    DESCRIPTION = "Add data to an existing brain database."

    p = subparser.add_parser("add",
                             description=DESCRIPTION,
                             help=DESCRIPTION,
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument('name', type=str, help='name of the brain database')
    p.add_argument('config', type=str, help='contained in a JSON file')


def build_subcommand_eval(subparser):
    DESCRIPTION = "Evaluate data given an existing brain database."

    p = subparser.add_parser("eval",
                             description=DESCRIPTION,
                             help=DESCRIPTION,
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument('name', type=str, help='name of the brain database')
    p.add_argument('config', type=str, help='contained in a JSON file')
    p.add_argument('-k', type=int, help='consider at most K nearest-neighbors')


def build_subcommand_map(subparser):
    DESCRIPTION = "Create a color map for a brain given an existing brain database."

    p = subparser.add_parser("map",
                             description=DESCRIPTION,
                             help=DESCRIPTION,
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument('name', type=str, help='name of the brain database')
    p.add_argument('config', type=str, help='contained in a JSON file')
    p.add_argument('--id', type=int, help='map only brain #id')
    p.add_argument('-k', type=int, help='consider at most K nearest-neighbors', default=100)
    p.add_argument('--prefix', type=str, help="prefix for the name of the results files", default="")
    p.add_argument('--radius', type=int, help="only look at neighbors within a certain radius")


def build_subcommand_vizu(subparser):
    DESCRIPTION = "Run some vizu for a brain given an existing brain database."

    p = subparser.add_parser("vizu",
                             description=DESCRIPTION,
                             help=DESCRIPTION,
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument('name', type=str, help='name of the brain database')
    p.add_argument('config', type=str, help='contained in a JSON file')


def build_subcommand_check(subparser):
    DESCRIPTION = "Check candidates distribution given an existing brain database."

    p = subparser.add_parser("check",
                             description=DESCRIPTION,
                             help=DESCRIPTION,
                             formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    p.add_argument('names', type=str, nargs='*', help='name of the brain database')
    #p.add_argument('config', type=str, nargs='?', help='contained in a JSON file')
    #p.add_argument('-m', dest="min_nonempty", type=int, help='consider only patches having this minimum number of non-empty voxels')


def buildArgsParser():
    DESCRIPTION = "Script to perform brain searches."
    p = argparse.ArgumentParser(description=DESCRIPTION)

    p.add_argument('--storage', type=str, default="redis", help='which storage to use: redis, memory, file')
    p.add_argument('--dir', type=str, default="./", help='folder where to store brain databases (where applicable)')

    p.add_argument('--spatial_weight', type=float, help='weight of the spatial position in a patch hashcode', default=0.)
    p.add_argument('-m', dest="min_nonempty", type=float, help='consider only patches having this minimum percent of non-empty voxels')
    p.add_argument('-r', dest="resampling_factor", type=float, help='resample image before processing', default=1.)
    p.add_argument('--skip', metavar="N", type=int, help='skip N images', default=0)
    p.add_argument('--norm', dest="do_normalization", action="store_true", help='perform histogram equalization')

    subparser = p.add_subparsers(title="brain_search commands", metavar="", dest="command")
    build_subcommand_list(subparser)
    build_subcommand_init(subparser)
    build_subcommand_add(subparser)
    build_subcommand_eval(subparser)
    build_subcommand_map(subparser)
    build_subcommand_vizu(subparser)
    build_subcommand_check(subparser)
    build_subcommand_clear(subparser)

    return p


def proportion_test_map(positives, negatives, ratio_pos):
    P = ratio_pos
    N = positives + negatives
    voxel_std = np.sqrt(P*(1-P)/N)
    probs = positives / N
    Z = (probs-P) / voxel_std
    return Z


def proportion_map(positives, negatives, ratio_pos):
    N = positives + negatives
    proportions = positives / N
    return np.nan_to_num(proportions)


def hack_map(positives, negatives, ratio_pos):
    ratio_neg = 1. - ratio_pos
    N = positives + negatives

    # Assume binary classification for now
    nb_neg = 1./(1. + negatives)
    nb_pos = 1./(1. + positives)

    pos = nb_pos * ratio_neg
    neg = nb_neg * ratio_pos
    m = (pos-neg) / N
    idx = m > 0
    m[idx] /= ratio_neg
    m[np.bitwise_not(idx)] /= ratio_pos

    return (m+1)/2.


def save_nifti(image, affine, name):
    nifti = nib.Nifti1Image(image, affine)
    nib.save(nifti, name)


def main(brain_manager=None):
    parser = buildArgsParser()
    args = parser.parse_args()

    readonly = args.command not in ["init", "add", "clear"]

    if brain_manager is None:
        brain_manager = BrainDatabaseManager(args.storage, dir=args.dir, readonly=readonly)

    # Build processing pipeline
    pipeline = BrainPipelineProcessing()
    if args.do_normalization:
        pipeline.add(BrainNormalization(type=0))
    if args.resampling_factor > 1:
        pipeline.add(BrainResampling(args.resampling_factor))

    if args.command == "list":
        framework.list(brain_manager, args.name, verbose=args.v, check_integrity=args.f)
    elif args.command == "clear":
        with Timer("Clearing"):
            framework.clear(brain_manager, args.names, force=args.f)

    elif args.command == "init":
        print "Creating brain database {}...".format(args.name)
        if args.name in brain_manager:
            print ("This database already exists. Please use command "
                   "'bench_hashing.py --storage {} clear -f {}' before.".format(args.storage, args.name))
            exit(-1)

        start = time.time()
        patch_shape = tuple(map(int, args.shape.split(",")))

        def _get_all_patches():
            config = json.load(open(args.trainset))
            brain_data = brain_data_factory(config, pipeline=pipeline)
            for brain_id, brain in enumerate(brain_data):
                print "ID: {0}/{1}".format(brain_id, len(brain_data))
                brain_patches = brain.extract_patches(patch_shape, min_nonempty=args.min_nonempty)
                vectors = brain_patches.create_vectors(spatial_weight=args.spatial_weight)
                yield vectors

        dimension = np.prod(patch_shape)
        if args.spatial_weight:
            dimension += len(patch_shape)

        hash_params = {}
        if args.SH is not None:
            hashtype, nbits = "SH", args.SH
            hash_params['trainset'] = _get_all_patches
            hash_params['pca_pkl'] = args.pca_pkl
            hash_params['bounds_pkl'] = args.bounds_pkl
        elif args.PCA is not None:
            hashtype, nbits = "PCA", args.PCA
            hash_params['trainset'] = _get_all_patches
            hash_params['pca_pkl'] = args.pca_pkl
        elif args.LSH is not None:
            hashtype, nbits = "LSH", args.LSH
        else:
            print "Must provide one of the following options: --SH, --LSH or --PCA"
            exit(-1)

        hashing = framework.hashing_factory(hashtype, dimension, nbits, **hash_params)
        framework.init(brain_manager, args.name, patch_shape, hashing)

        print "Created in {0:.2f} sec.".format(time.time()-start)

    elif args.command == "add":
        config = json.load(open(args.config))
        brain_data = brain_data_factory(config, pipeline=pipeline)
        framework.add(brain_manager, args.name, brain_data,
                      min_nonempty=args.min_nonempty,
                      spatial_weight=args.spatial_weight)

    elif args.command == "check":
        names = args.names
        if len(args.names) == 0:
            names = brain_manager.brain_databases_names

        for name in names:
            try:
                print "\n" + name
                framework.check(brain_manager, name,
                                spatial_weight=args.spatial_weight)
            except Exception as e:
                print e.message

    elif args.command == "eval":
        brain_database = brain_manager[args.name]
        if brain_database is None:
            raise ValueError("Unexisting brain database: " + args.name)

        patch_shape = tuple(brain_database.config['shape'])
        config = json.load(open(args.config))
        brain_data = brain_data_factory(config)

        print 'Evaluating...'

        def majority_vote(candidates):
            return np.argmax(np.mean([np.array(c['data']['target']) for c in candidates], axis=0))

        def weighted_majority_vote(candidates):
            votes = [np.exp(-c['dist']) * np.array(c['data']['target']) for c in candidates]
            return np.argmax(np.mean(votes, axis=0))

        brain_database.engine.distance = EuclideanDistance()

        #neighbors = []
        nb_neighbors = 0
        start = time.time()
        nb_success = 0.0
        nb_patches = 0
        for brain_id, (brain, label) in enumerate(brain_data):
            patches_and_pos = get_patches(brain, patch_shape=patch_shape, min_nonempty=args.min_nonempty)
            patches = flattenize((patch for patch, pos in patches_and_pos))

            start_brain = time.time()
            neighbors_per_patch = brain_database.query(patches)
            nb_patches += len(neighbors_per_patch)
            brain_neighbors = list(chain(*neighbors_per_patch))
            print "Brain #{0} ({3:,} patches), found {1:,} neighbors in {2:.2f} sec.".format(brain_id, len(brain_neighbors), time.time()-start_brain, len(neighbors_per_patch))

            #prediction = weighted_majority_vote(brain_neighbors)
            prediction = majority_vote(brain_neighbors)
            nb_success += prediction == np.argmax(label)

            nb_neighbors += len(brain_neighbors)
            del brain_neighbors
            #neighbors.extend(brain_neighbors)

        nb_brains = brain_id + 1
        print "Found a total of {0:,} neighbors for {1} brains ({3:,} patches) in {2:.2f} sec.".format(nb_neighbors, nb_brains, time.time()-start, nb_patches)
        print "Classification error: {:2.2f}%".format(100 * (1. - nb_success/nb_brains))

    elif args.command == "map":
        config = json.load(open(args.config))
        brain_data = brain_data_factory(config, pipeline=pipeline, id=args.id)
        framework.create_map(brain_manager, args.name, brain_data, K=args.k,
                             min_nonempty=args.min_nonempty,
                             spatial_weight=args.spatial_weight)

    elif args.command == "vizu":
        from brainsearch.vizu_chaco import NoisyBrainsearchViewer

        brain_db = brain_manager[args.name]
        if brain_db is None:
            raise ValueError("Unexisting brain database: " + args.name)

        patch_shape = brain_db.metadata['patch'].shape
        config = json.load(open(args.config))
        brain_data = brain_data_factory(config, pipeline=pipeline)

        for brain_id, brain in enumerate(brain_data):
            print 'Viewing brain #{0} (label: {1})'.format(brain_id, brain.label)
            patches, positions = brain.extract_patches(patch_shape, min_nonempty=args.min_nonempty, with_positions=True)

            query = {'patches': patches,
                     'positions': positions,
                     'patch_size': patch_shape}
            viewer = NoisyBrainsearchViewer(query, brain_db.engine, brain_voxels=brain.image)
            viewer.configure_traits()

    return brain_manager


if __name__ == '__main__':
    main()
    # try:
    #     db_manager = main()
    # except:
    #     import traceback
    #     traceback.print_exc()
    #     exit(-1)
