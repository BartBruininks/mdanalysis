# -*- Mode: python; tab-width: 4; indent-tabs-mode:nil; -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
#
# MDAnalysis --- http://mdanalysis.googlecode.com
# Copyright (c) 2006-2011 Naveen Michaud-Agrawal,
#               Elizabeth J. Denning, Oliver Beckstein,
#               and contributors (see website for details)
# Released under the GNU Public Licence, v2 or any higher version
#
# Please cite your use of MDAnalysis in published work:
#
#     N. Michaud-Agrawal, E. J. Denning, T. B. Woolf, and
#     O. Beckstein. MDAnalysis: A Toolkit for the Analysis of
#     Molecular Dynamics Simulations. J. Comput. Chem. 32 (2011), 2319--2327,
#     doi:10.1002/jcc.21787
#


"""TRZ trajectory I/O  --- :mod:`MDAnalysis.coordinates.TRZ`
============================================================
 
Classes to read IBIsCO/YASP binary trajectories.
  
Reads coordinates, velocities and more.  

References 
------------

.. _IBIsCO: http://www.theo.chemie.tu-darmstadt.de/ibisco/IBISCO.html

.. _YASP: http://www.theo.chemie.tu-darmstadt.de/group/services/yaspdoc/yaspdoc.html

"""

import os, errno
import base
from base import Timestep
import MDAnalysis.core
import numpy
import struct
from MDAnalysis.coordinates.core import triclinic_box

class Timestep(base.Timestep):
    """ TRZ custom Timestep

    :Attributes:
      ``frame``
        Index of the frame, (1 based)
      ``numatoms``
        Number of atoms in the frame (will be constant through trajectory)
      ``time``
        Current time of the system in ps (will not always start at 0)
      ``pressure``
        Pressure of the system box in kPa
      ``pressure_tensor``
        Array containing pressure tensors in order: xx, xy, yy, xz, yz, zz 
      ``total_energy``
        Hamiltonian for the system in kJ/mol
      ``potential_energy``
        Potential energy of the system in kJ/mol
      ``kinetic_energy``
        Kinetic energy of the system in kJ/mol
      ``temperature``
        Temperature of the system in Kelvin

    :Private Attributes:
      ``_unitcell``
        Unitcell for system. [Lx, 0.0, 0.0, 0.0, Ly, 0.0, 0.0, 0.0, Lz]
      ``_pos``
        Position of particles in box (native nm)
      ``_velocities``
        Velocities of particles in box (native nm/ps)
    """
    def __init__(self, arg):
        if numpy.dtype(type(arg)) == numpy.dtype(int):
            self.frame = 0
            self.numatoms = arg
            self.time = 0.0 #System time in ps
            self.pressure = 0.0 #pressure in kPa
            self.pressure_tensor = numpy.zeros((6), dtype=numpy.float32) #ptxx, ptxy, ptyy, ptxz, ptyz, ptzz
            self.total_energy = 0.0 # Energies all kJ mol-1
            self.potential_energy = 0.0
            self.kinetic_energy = 0.0
            self.temperature = 0.0 #Temperature in Kelvin
            self._pos        = numpy.zeros((self.numatoms, 3), dtype=numpy.float32, order ='F')
            self._velocities = numpy.zeros((self.numatoms, 3), dtype=numpy.float32, order ='F')
            self._unitcell   = numpy.zeros((9),                dtype=numpy.float32, order ='F') 
        elif isinstance(arg, Timestep): # Copy constructor
            # This makes a deepcopy of the timestep
            self.frame = arg.frame
            self.numatoms = arg.numatoms
            self.time = arg.time
            self.pressure = arg.pressure
            self.pressure_tensor = numpy.array(arg.pressure_tensor)
            self.total_energy = arg.total_energy
            self.potential_energy = arg.potential_energy
            self.kinetic_energy = arg.kinetic_energy
            self.temperature = arg.temperature
            self._unitcell = numpy.array(arg._unitcell)
            self._pos = numpy.array(arg._pos, order='F')
            self._velocities = numpy.array(arg._velocities, order='F')
        elif isinstance(arg, numpy.ndarray):
            if len(arg.shape) != 2:
                raise ValueError("numpy array can only have 2 dimensions")
            self._unitcell = numpy.zeros((9), dtype=numpy.float32)
            self.frame = 0
            if arg.shape[1] == 3:
                self.numatoms = arg.shape[0]
            else:
                self.numatoms = arg.shape[0]
                # Or should an exception be raised if coordinate
                # structure is not 3-dimensional? Maybe velocities
                # could be read one day... [DP]
            self._pos = arg.astype(numpy.float32).copy('Fortran',)
        else:
            raise ValueError("Cannot create an empty Timestep")
        self._x = self._pos[:,0]
        self._y = self._pos[:,1]
        self._z = self._pos[:,2]  

    @property
    def dimensions(self):
        """
        Unit cell dimensions, native format is

        """
        x = self._unitcell[0:3]
        y = self._unitcell[3:6]
        z = self._unitcell[6:9]
        return triclinic_box(x,y,z)

class TRZReader(base.Reader):
    """ Reads an IBIsCO or YASP trajectory file 

    :Data:
        ts
          :class:`~MDAnalysis.coordinates.TRZ.Timestep` object
          containing coordinates of current frame
        
    :Methods:
      ``len(trz)``
        returns the number of frames
      ``for ts in trz``
        iterates through the trajectory

    :Format:
      TRZ format detailed below, each line is a single fortran write statement, so is surrounded by 4 bytes of metadata
      In brackets after each entry is the size of the content of each line ::
        ``Header`` 
          title(80c)
          nrec (int4)
        ``Frame``
          nframe, ntrj*nframe, natoms, treal (3*int4, real8)
          boxx, 0.0, 0.0, 0.0, boxy, 0.0, 0.0, 0.0, boxz (real8 * 9)
          pressure, pt11, pt12, pt22, pt13, pt23, pt33 (real8 *7)
          6, etot, ptot, ek, t, 0.0, 0.0 (int4, real8 * 6)
          rx (real4 * natoms)
          ry 
          rz
          vx
          vy
          vz
"""

    format = "TRZ"

    units = {'time':'ps', 'length':'nm', 'velocity':'nm/ps'}

    def __init__(self, trzfilename, numatoms=None, convert_units=None, **kwargs):
        """Creates a TRZ Reader

        :Arguments:
          *trzfilename*
            name of input file
          *numatoms*
            number of atoms in trajectory, must taken from topology file!
          *convert_units*
            converts units to MDAnalysis defaults
            """
        if numatoms is None:
            raise ValueError('TRZReader requires the numatoms keyword')

        if convert_units is None:
            convert_units = MDAnalysis.core.flags['convert_gromacs_lengths']
        self.convert_units = convert_units

        self.filename = trzfilename
        self.trzfile = open(self.filename, 'rb')

        self.__numatoms = numatoms
        self.__numframes = None
        self.__delta = None

        self.fixed = 0 #Are any atoms fixed in place? Not used in trz files
        self.skip = 1 #Step size for iterating through trajectory
        self.periodic = False # Box info for PBC
        self.skip_timestep = 1 # Number of steps between frames, can be found in trz files

        self._read_trz_header()
        self.ts = Timestep(self.numatoms)
        self._read_next_timestep()

    def _read_trz_header(self):
        """Reads the header of the trz trajectory"""
        #Read the header of the file
        #file.read(4)
        #title = struct.unpack('80c',file.read(80))
        #file.read(4)
        #file.read(4)
        #nrec = struct.unpack('i',file.read(4))
        #file.read(4)
        self.trzfile.seek(100,1) # Header is 100 bytes in total, but contains nothing "useful"

    def _read_next_timestep(self, ts=None): # self.next() is from base Reader class and calls this
        #Read a timestep from binary file
        if ts is None:
            ts = self.ts

        try:
            #Skip into frame
            self.trzfile.seek(12,1) # Seek forward 12 bytes from current position (1)
            natoms = struct.unpack('i',self.trzfile.read(4))[0]
            ts.time = struct.unpack('d',self.trzfile.read(8))[0] # Real time of the system
            #Read box data
            self.trzfile.seek(8,1) #Includes 4 from previous write statement
            ts._unitcell[:] = struct.unpack('9d',self.trzfile.read(72)) #3x3 matrix with lengths along diagonal
            self.trzfile.seek(4,1)
            #Pressure data
            self.trzfile.seek(4,1)
            ts.pressure = struct.unpack('d',self.trzfile.read(8))
            ts.pressure_tensor[:] = struct.unpack('6d',self.trzfile.read(8*6))
            self.trzfile.seek(4,1)
            #Energy data
            self.trzfile.seek(8,1) #4 byte buffer + meaningless integer skip
            ts.total_energy = struct.unpack('d',self.trzfile.read(8))
            ts.potential_energy = struct.unpack('d',self.trzfile.read(8))
            ts.kinetic_energy = struct.unpack('d',self.trzfile.read(8))
            ts.temperature = struct.unpack('d',self.trzfile.read(8))
            self.trzfile.seek((2*8+4),1) #2 empty doubles and 4 byte end buffer
            #Read coordinate data
            readarg = str(natoms) + 'f' #Argument for struct.unpack
            self.trzfile.seek(4,1)
            ts._x[:] = struct.unpack(readarg,self.trzfile.read(4*natoms)) # ts._pos[:,0] = x coord
            self.trzfile.seek(8,1)
            ts._y[:] = struct.unpack(readarg,self.trzfile.read(4*natoms))
            self.trzfile.seek(8,1)
            ts._z[:] = struct.unpack(readarg,self.trzfile.read(4*natoms))
            self.trzfile.seek(4,1)
            #Velocities
            self.trzfile.seek(4,1)
            ts._velocities[:,0] = struct.unpack(readarg,self.trzfile.read(4*natoms))
            self.trzfile.seek(8,1)
            ts._velocities[:,1] = struct.unpack(readarg,self.trzfile.read(4*natoms))
            self.trzfile.seek(8,1)
            ts._velocities[:,2] = struct.unpack(readarg,self.trzfile.read(4*natoms))         
            self.trzfile.seek(4,1)

            ts.frame += 1

            if self.convert_units: #Convert things read into MDAnalysis' native formats (nm -> angstroms in this case)
                self.convert_pos_from_native(self.ts._pos)
                self.convert_pos_from_native(self.ts._unitcell)
                self.convert_velocities_from_native(self.ts._velocities)

            return ts
        except struct.error: #End of file reached if struct fails to unpack
            raise IOError

    @property
    def numatoms(self):
        """Number of atoms in a frame"""
        if not self.__numatoms is None:
            return  self.__numatoms
        try:
            self._reopen()
            self.__numatoms = self._read_trz_natoms(self.trzfile)
        except IOError:
            return 0
        else:
            return self.__numatoms

    def _read_trz_natoms(self, f):
        #Read start of next frame and reopen file
        try:
            f.seek(12,1) #Reads 4 bytes at start, then nframe, ntrj*nframe
            natoms = struct.unpack('i',f.read(4))
        except struct.error:
            raise IOError
        else:
            self._reopen()
            return natoms

    @property
    def numframes(self):
        """Total number of frames in a trajectory"""
        if not self.__numframes is None:
            return self.__numframes
        try:
            self.__numframes = self._read_trz_numframes(self.trzfile)
        except IOError:
            return 0
        else:
            return self.__numframes

    def _read_trz_numframes(self, trzfile):
        framecounter = 0
        self._reopen()
        while True:
            try:
                self._read_next_timestep()
                framecounter += 1
            except IOError:
                self.rewind()
                return framecounter

    @property
    def delta(self):
        """Time step between frames in ps

        Assumes that this step is constant (ie. 2 trajectories with different steps haven't been
        stitched together)
        Returns 0 in case of IOError
        """
        if not self.__delta is None:
            return self.__delta
        try:
            t0 = self.ts.time
            self.next()
            t1 = self.ts.time
            self.__delta = t1 - t0
        except IOError:
            return 0
        finally:
            self.rewind()
        return self.__delta

    def __iter__(self):
        self.ts.frame = 0
        self._reopen()
        while True:
            try:
                yield self._read_next_timestep()
            except IOError:
                self.rewind()
                raise StopIteration

    def rewind(self):
        """Reposition reader onto first frame"""
        self._reopen()
        self.next()

    def _reopen(self):
        self.close()
        self.open_trajectory()
        self._read_trz_header() # Moves to start of first frame

    def open_trajectory(self):
        """Open the trajectory file"""
        if not self.trzfile is None:
            raise IOError(errno.EALREADY, 'TRZ file already opened', self.filename)
        if not os.path.exists(self.filename):
            raise IOError(errno.ENOENT, 'TRZ file not found', self.filename)

        self.trzfile = file(self.filename, 'rb')

        #Reset ts
        ts = self.ts
        ts.status = 1
        ts.frame =0
        ts.step = 0
        ts.time = 0
        return self.trzfile

    def close(self):
        """Close trz file if it was open"""
        if self.trzfile is None:
            return
        self.trzfile.close()
        self.trzfile = None

    def __del__(self):
        if not self.trzfile is None:
            self.close()
