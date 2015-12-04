# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 fileencoding=utf-8
#
# MDAnalysis --- http://www.MDAnalysis.org
# Copyright (c) 2006-2015 Naveen Michaud-Agrawal, Elizabeth J. Denning, Oliver Beckstein
# and contributors (see AUTHORS for the full list)
#
# Released under the GNU Public Licence, v2 or any higher version
#
# Please cite your use of MDAnalysis in published work:
# N. Michaud-Agrawal, E. J. Denning, T. B. Woolf, and O. Beckstein.
# MDAnalysis: A Toolkit for the Analysis of Molecular Dynamics Simulations.
# J. Comput. Chem. 32 (2011), 2319--2327, doi:10.1002/jcc.21787
#

"""
GRO topology parser
===================

Read a list of atoms from a GROMOS/Gromacs GRO coordinate file to
build a basic topology.

Atom types, masses and charges are guessed.

.. SeeAlso:: :mod:`MDAnalysis.coordinates.GRO`

Classes
-------

.. autoclass:: GROParser
   :members:
   :inherited-members:

"""
from __future__ import absolute_import

import numpy as np

from ..lib.util import openany
from ..core.AtomGroup import Atom
from ..core.topologyattrs import (
    Resids,
    Resnames,
    Atomids,
    Atomnames,
)
from ..core.topology import Topology
from .core import get_atom_mass, guess_atom_charge, guess_atom_element
from .base import TopologyReader, squash_by, remap_ids


class GROParser(TopologyReader):
    def parse(self):
        """Parse GRO file *filename* and return the dict `structure`.

        Only reads the list of atoms.

        :Returns: MDAnalysis internal *structure* dict

        .. SeeAlso:: The *structure* dict is defined in
                     :func:`MDAnalysis.topology.base`.
        """
        segid = "SYSTEM"
        atoms = []
        with openany(self.filename, "r") as grofile:
            grofile.readline()
            natoms = int(grofile.readline())
            for atom_iter in xrange(natoms):
                line = grofile.readline()
                try:
                    resid, resname, name = int(line[0:5]), line[5:10].strip(), line[10:15].strip()
                    # guess based on atom name
                    elem = guess_atom_element(name)
                    atype = elem
                    mass = get_atom_mass(elem)
                    charge = guess_atom_charge(name)
                    # segid = "SYSTEM"
                    # ignore coords and velocities, they can be read by coordinates.GRO
                except:
                    raise IOError("Couldn't read the following line of the .gro file:\n"
                                  "{0}".format(line))
                else:
                    # Just use the atom_iter (counting from 0) rather than
                    # the number in the .gro file (which wraps at 99999)
                    atoms.append(Atom(atom_iter, name, atype, resname, resid,
                                      segid, mass, charge, universe=self._u))
        structure = {'atoms': atoms}

        return structure


class NewGROParser(TopologyReader):
    def parse(self):
        """Return the *Topology* object for this file"""
        # Gro has the following columns
        # resid, resname, name, index, (x,y,z)
        with openany(self.filename, 'r') as inf:
            inf.readline()
            n_atoms = int(inf.readline())

            # Allocate shizznizz
            resids = np.zeros(n_atoms, dtype=np.int32)
            resnames = np.zeros(n_atoms, dtype=object)
            names = np.zeros(n_atoms, dtype=object)
            indices = np.zeros(n_atoms, dtype=np.int32)

            for i in xrange(n_atoms):
                line = inf.readline()
                resids[i] = int(line[:5])
                resnames[i] = line[5:10].strip()
                names[i] = line[10:15].strip()
                indices[i] = int(line[15:20])

        new_resids, (new_resnames,) = squash_by(resids, resnames)

        # new_resids is len(residues)
        # so resindex 0 has resid new_resids[0]

        # Renumber the (AtomID: ResID) relationship to be (AtomID: ResIX)
        residx = remap_ids(resids, new_resids)

        atomnames = Atomnames(names)
        residueids = Resids(new_resids)
        residuenames = Resnames(new_resnames)

        top = Topology(n_atoms, len(new_resids), 1,
                       attrs=[atomnames, residueids, residuenames],
                       Rixs=residx,
                       Sixs=None)

        return top
        
