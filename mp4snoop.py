#
# ISO Base Media File Format / MP4 parser
#
# 2018 Brent Burton
#
# See LICENSE file for license details.
#
# Modify the mp4.open() at the bottom of this file
# to read a file.

import struct
import os

# Simple indented-print functions:
indent = 0

def ipush():
    global indent
    indent += 1

def ipop():
    global indent
    if indent > 0:
        indent -= 1

def iprint(msg):
    global indent
    "Print already-formatted msg with indentation"
    print(('    ' * indent) + msg)


# The ISOBMFF class encapsulates the ISO 14496-12/14 file format.
#
# Instantiate, open(), scan(), close()
#
class ISOBMFF(object):
    def __init__(self):
        self.filename = None            # name of file opened
        self.file = None                # opened file object
        self.filesize = 0

    def open(self, filename):
        self.file = open(filename, 'rb')
        # record file size by a quick seek
        self.file.seek(0, os.SEEK_END)
        self.filesize = self.file.tell()
        self.file.seek(0, os.SEEK_SET)

    def close(self):
        if self.file:
            self.file.close()
        self.file = None
        self.filename = None
        self.filesize = 0

    def scan(self):
        "Scan an opened file, print toplevel boxes encountered"
        if not self.file:
            raise IOError, "No open file in ISOBMFF"
        # Begin scanning. Read next box's size and type.
        self.file.seek(0, os.SEEK_SET)
        numBoxes = 0
        while self.file.tell() < self.filesize:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break

            # TODO, MAYBE: if boxtype == 'uuid' then read 16-byte extended type
            numBoxes += 1
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            # Parse out recognized boxes
            if boxtype == 'ftyp':
                self.scan_ftyp(skip)
            elif boxtype == 'moov':
                self.scan_moov(skip)
            else:                       # else skip past this box
                self.file.seek(skip, os.SEEK_CUR)
            print("")
        iprint("%d boxes scanned" % (numBoxes))

    def scan_uint16(self):
        "read 2 bytes as uint16"
        return struct.unpack('>H', self.file.read(2))[0]

    def scan_int16(self):
        "read 2 bytes as int16"
        return struct.unpack('>h', self.file.read(2))[0]

    def scan_uint16_3(self):
        "read 3 uint16, return as list"
        return struct.unpack('>3H', self.file.read(6))

    def scan_uint32(self):
        "read 4 bytes as uint32"
        return struct.unpack('>I', self.file.read(4))[0]

    def scan_int32(self):
        "read 4 bytes as int32"
        return struct.unpack('>i', self.file.read(4))[0]

    def scan_uint64(self):
        "read 8 bytes as uint64"
        return struct.unpack('>Q', self.file.read(8))[0]

    def scan_int64(self):
        "read 4 bytes as int64"
        return struct.unpack('>q', self.file.read(8))[0]

    def scan_fourcc(self):
        return struct.unpack('4s', self.file.read(4))[0]

    def scan_string(self):
        "Read UTF8 characters at current file position until 0x0 is found"
        c = 1
        s = ""
        while c:
            c = ord(self.file.read(1)[0])
            if not c:
                break
            s += chr(c)
        return s

    def scan_string_len(self):
        "Read UTF8 pascal-style string: len byte, len*characters"
        length = ord(self.file.read(1)[0])
        s = self.file.read(length)
        return s

# Files consist of boxes, boxes can contain other boxes (chunks)
# A Box is a chunk with a 32bit size, and 32bit type, with data following.
# A Full Box is a Box with 8bit version and 24bit flags fields.
#
# A container box has the sole purpose of contain and group related boxes.

    def scan_box(self):
        "Returns tuple (boxsize,boxtype,remaining)"
        # boxsize is overall, total box size.
        # 'remaining' is how many bytes are left to read of this box
        boxsize = self.scan_uint32()
        boxtype = self.scan_fourcc()
        if boxsize == 1:            # then use extended 64bit size
            boxsize = self.scan_uint64()
            skip = boxsize - 16
        elif boxsize == 0:          # then it is remainder of file (and last box of file)
            curpos = self.file.tell()
            boxsize = (self.filesize - curpos) + 8
            skip = boxsize - 8
        else:                       # Else original 32bit length was valid
            skip = boxsize - 8
        return (boxsize,boxtype,skip)

    def scan_fullbox(self, remaining):
        "scan a FullBox's version and flags. Return them and update remaining bytes in chunk"
        # OK, version is one byte, followed by three bytes of flags.
        # Read as big-endian I, then split with bitmasks
        verflags = self.scan_uint32()
        version = (verflags >> 24) & 0x00FF
        flags = verflags & 0x00FFFFFF
        return (version, flags, remaining-4)

    def scan_ftyp(self, remaining):
        "File Type - 4.3 - Box"
        majorBrand = self.scan_fourcc()
        minorVersion = self.scan_uint32()
        remaining -= 8
        ipush()
        iprint("major brand: '%s'" % (majorBrand))
        iprint("minor version: %u" % (minorVersion))
        while remaining > 0:
            brand = self.scan_fourcc()
            iprint("compat brand: '%s'" % (brand))
            remaining -= 4
        ipop()

    def scan_moov(self, remaining):
        "Movie Box - 8.1 - Box, Container"
        ipush()
        chunkend = self.file.tell() + remaining
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            if boxtype == 'mvhd':
                self.scan_mvhd(skip)
            elif boxtype == 'trak':
                self.scan_trak(skip)
            elif boxtype == 'udta':
                self.scan_udta(skip)
            else:
                self.file.seek(skip, os.SEEK_CUR)
        ipop()

    def scan_mvhd(self, remaining):
        "MovieHeaderBox - 8.3 - FullBox"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        if version == 1:
            creationTime = self.scan_uint64()
            modificationTime = self.scan_uint64()
            timescale = self.scan_uint32() # yep, 32bits
            duration = self.scan_uint64()
        else: # version == 0
            creationTime = self.scan_uint32()
            modificationTime = self.scan_uint32()
            timescale = self.scan_uint32()
            duration = self.scan_uint32()
        iprint("creation = %u" % creationTime)
        iprint("modification = %u" % modificationTime)
        iprint("timescale = %u" % timescale)
        iprint("duration = %u" % duration)
        rate = self.scan_uint32()
        volume = self.scan_uint16()
        iprint("rate = 0x%08x" % rate)
        iprint("volume = 0x%04x" % volume)
        # reserved: 2 + 4 + 4 = 10
        self.file.seek(10, os.SEEK_CUR)
        matrix = struct.unpack('>9l', self.file.read(9*4))
        iprint("matrix = %s" % str(matrix))
        # uint32[6] pre_defined = 24
        self.file.seek(24, os.SEEK_CUR)
        nextTrackID = self.scan_uint32()
        iprint("nextTrackID = %d" % nextTrackID)
        ipop()

    def scan_trak(self, remaining):
        "Track Box - 8.4 - Box, Container"
        ipush()
        chunkend = self.file.tell() + remaining
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            if boxtype == 'tkhd':
                self.scan_tkhd(skip)
            elif boxtype == 'mdia':
                self.scan_mdia(skip)
            elif boxtype == 'edts':
                self.scan_edts(skip)
            elif boxtype == 'udta':
                self.scan_udta(skip)
            else:
                self.file.seek(skip, os.SEEK_CUR)
        ipop()

    def scan_tkhd(self, remaining):
        "Track Header Box - 8.5 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        if version == 1:
            creationTime = self.scan_uint64()
            modificationTime = self.scan_uint64()
            trackID = self.scan_uint32() # yep, 32bits
            reserved = self.scan_uint32() # yep, 32bits
            duration = self.scan_uint64()
        else: # version == 0
            creationTime = self.scan_uint32()
            modificationTime = self.scan_uint32()
            trackID = self.scan_uint32()
            reserved = self.scan_uint32()
            duration = self.scan_uint32()
        iprint("creation = %u" % creationTime)
        iprint("modification = %u" % modificationTime)
        iprint("trackID = %u" % trackID)
        iprint("duration = %u" % duration)
        # int32[2] reserved
        self.file.seek(2*4, os.SEEK_CUR)
        layer = self.scan_int16()
        alternateGroup = self.scan_uint16()
        volume = self.scan_int16()
        reserved = self.scan_int16()
        iprint("layer = %d" % (layer))
        iprint("altGroup = %d" % (alternateGroup))
        iprint("volume = 0x%04x" % (volume))
        matrix = struct.unpack('>9l', self.file.read(9*4))
        iprint("matrix = %s" % str(matrix))
        width = self.scan_int32()
        height = self.scan_int32()
        iprint("width = %d" % (width))
        iprint("height = %d" % (height))
        ipop()

    def scan_mdia(self, remaining):
        "Media Box - 8.7 - Box, Container"
        ipush()
        chunkend = self.file.tell() + remaining
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            if boxtype == 'mdhd':
                self.scan_mdhd(skip)
            elif boxtype == 'hdlr':
                self.scan_hdlr(skip)
            elif boxtype == 'minf':
                self.scan_minf(skip)
            else:
                self.file.seek(skip, os.SEEK_CUR)
        ipop()

    def scan_mdhd(self, remaining):
        "Media Header Box - 8.8 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        if version == 1:
            creationTime = self.scan_uint64()
            modificationTime = self.scan_uint64()
            timescale = self.scan_uint32() # yep, 32bits
            duration = self.scan_uint64()
        else: # version == 0
            creationTime = self.scan_uint32()
            modificationTime = self.scan_uint32()
            timescale = self.scan_uint32()
            duration = self.scan_uint32()
        iprint("creation = %u" % creationTime)
        iprint("modification = %u" % modificationTime)
        iprint("timescale = %u" % timescale)
        iprint("duration = %u" % duration)
        # language is 0:reserved, 5:char1, 5:char2, 5:char3 = 3 char language code/string
        language = self.scan_uint16()
        #iprint("language = 0x%04x" % language)
        iprint("language = %c%c%c" % (chr(((language >> 10) & 0x001F) + 0x60), chr(((language >> 5) & 0x001F) + 0x60), chr((language & 0x1F) + 0x60)))
        pre_defined = self.scan_uint16()  # const 0, ignore.
        ipop()

    def scan_hdlr(self, remaining):
        "Handler Reference Box - 8.9 - Full Box"
        ipush()
        # record end of the box for scanning name, see below.
        endpos = self.file.tell() + remaining
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        # only version 0 in spec, so nothing to check
        pre_defined = self.scan_uint32()
        handlerType = self.scan_fourcc()
        iprint("handlerType = '%s'" % handlerType)
        self.file.seek(4*3, os.SEEK_CUR) # 3 reserved uint32
        #self.dumpBytes(20, 'hdlr name string')
        # The name here is scanned differently than calling
        # self.scan_string() because some action camera
        # manufacturers are not writing the name string per spec,
        # as a string of UTF8 chars followed by a null. Instead,
        # they are writing a 0x09, followed by 9 characters, with
        # no trailing null. ** The method of reading up to the
        # box end works here only because the name field is the
        # last field of this box. ** This does not impact
        # properly-encoded string fields.
        curpos = self.file.tell()
        name = self.file.read(endpos-curpos)
        iprint("name = '%s'" % name)
        ipop()

    def dumpBytes(self, length, msg):
        """Read next 'length' bytes and print them out with 'msg'.
        After output, the file object is rewound to where it was
        before this call."""
        curpos = self.file.tell()
        print("*** %s, offset: 0x%x=%u" % (msg, curpos, curpos))
        bytes = self.file.read(length)
        out = ""
        for b in bytes:
            out += "%02x " % ord(b)
        print("dump:  " + out)
        out = ""
        for b in bytes:
            char = b
            if 0 <= ord(b) < 32:
                char = '.'
            out += "%c  " % char
        print("ascii: " + out)
        self.file.seek(curpos, os.SEEK_SET)

    def scan_minf(self, remaining):
        "Media Information Box - 8.10 - Box"
        ipush()
        chunkend = self.file.tell() + remaining
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            if boxtype == 'dinf':
                self.scan_dinf(skip)
            elif boxtype == 'stbl':
                self.scan_stbl(skip)
            elif boxtype == 'vmhd':
                self.scan_vmhd(skip)
            elif boxtype == 'smhd':
                self.scan_smhd(skip)
            elif boxtype == 'hmhd':
                self.scan_hmhd(skip)
            elif boxtype == 'nmhd':
                self.scan_nmhd(skip)
            else:
                self.file.seek(skip, os.SEEK_CUR)
        ipop()

    def scan_vmhd(self, remaining):
        "Video Media Header Box - 8.11.2 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        # only version 0 in spec, so nothing to check
        # flags will have value 0x1 per spec, no semantic given.
        graphicsMode = self.scan_uint16()
        iprint("graphicsMode = %d" % graphicsMode)
        opcolor = self.scan_uint16_3()
        iprint("opcolor = RGB%s" % str(opcolor))
        ipop()

    def scan_smhd(self, remaining):
        "Sound Media Header Box - 8.11.3 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        # only version 0 in spec, so nothing to check
        balance = self.scan_int16()
        iprint("balance = %d / %.3f" % (balance, balance/16.0)) # FP 8.8
        reserved = self.scan_uint16()
        ipop()

    def scan_hmhd(self, remaining):
        "Hint Media Header Box - 8.11.4 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        # only version 0 in spec, so nothing to check
        maxPDUSize = self.scan_uint16()
        avgPDUSize = self.scan_uint16()
        maxbitrate = self.scan_uint32()
        avgbitrate = self.scan_uint32()
        reserved = self.scan_uint32()
        iprint("maxPDUSize = %d" % maxPDUSize)
        iprint("avgPDUSize = %d" % avgPDUSize)
        iprint("maxbitrate = %d" % maxbitrate)
        iprint("avgbitrate = %d" % avgbitrate)
        ipop()

    def scan_nmhd(self, remaining):
        "Null Media Header Box - 8.11.5 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        # only version 0 in spec, so nothing to check
        # no fields to parse
        ipop()

    def scan_dinf(self, remaining):
        "Data Information Box - 8.12 - Box"
        ipush()
        chunkend = self.file.tell() + remaining
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            if boxtype == 'dref':
                self.scan_dref(skip)
            else:
                self.file.seek(skip, os.SEEK_CUR)
        ipop()

    def scan_url_(self, remaining):
        "DataEntryURLBox - 8.13 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        # only version 0 in spec, so nothing to check
        # location data may be missing per 8.13.1
        if flags & 0x01:
            iprint("location = no location in URL")
        else:
            location = self.scan_string()
            iprint("location = '%s'" % location)
        ipop()

    def scan_urn_(self, remaining):
        "DataEntryURNBox - 8.13 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        # only version 0 in spec, so nothing to check
        name = self.scan_string()
        iprint("name = '%s'" % name)
        location = self.scan_string()
        iprint("location = '%s'" % location)
        ipop()

    def scan_dref(self, remaining):
        "DataReferenceBox - 8.13 - Full Box"
        ipush()
        chunkend = self.file.tell() + remaining
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        # only version 0 in spec, so nothing to check
        entryCount = self.scan_uint32()
        iprint("entryCount = %d" % entryCount)
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            if boxtype == 'url ':
                self.scan_url_(skip)
            elif boxtype == 'urn ':
                self.scan_urn_(skip)
            else:
                self.file.seek(skip, os.SEEK_CUR)
        ipop()

    def scan_stbl(self, remaining):
        "Sample Table - 8.14 - Box"
        ipush()
        chunkend = self.file.tell() + remaining
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            self.file.seek(skip, os.SEEK_CUR)
        ipop()

# 8.15.2 - stts full box, child of stbl
# 8.15.3 - ctts full box, child of stbl
# 8.16 - stsd full box, child of stbl. Several subtypes.
# 8.17.1 - stsz full box, child of stbl
# 8.17.2 - stz2 full box, child of stbl
# 8.18 - stsc full box, child of stbl
# 8.19 - stco/co64 box, child of stbl

    def scan_edts(self, remaining):
        "Edit Box - 8.25 - Box, Container"
        ipush()
        chunkend = self.file.tell() + remaining
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            if boxtype == 'elst':
                self.scan_elst(skip)
            else:
                self.file.seek(skip, os.SEEK_CUR)
        ipop()

    def scan_elst(self, remaining):
        "Edit List - 8.26 - Full Box"
        ipush()
        version,flags,skip = self.scan_fullbox(remaining)
        iprint('version = ' + str(version))
        iprint("flags = 0x%x" % (flags))
        entryCount = self.scan_uint32()
        iprint("entryCount = %d" % (entryCount))
        for i in range(entryCount):
            ipush()
            if version == 1:
                segmentDuration = self.scan_uint64()
                mediaTime = self.scan_int64()
            else: # version == 0
                segmentDuration = self.scan_uint32()
                mediaTime = self.scan_int32()
            mediaRateInt = self.scan_int16()
            mediaRateFraction = self.scan_int16()
            iprint("entry: %d" % (i))
            iprint("segmentDuration = %u" % (segmentDuration))
            iprint("mediaTime = %d" % (mediaTime))
            iprint("mediaRateInt = %d" % (mediaRateInt))
            iprint("mediaRateFrac = %d" % (mediaRateFraction))
            ipop()
        ipop()

    def scan_udta(self, remaining):
        "User Data - 8.27 - Box, Container"
        ipush()
        chunkend = self.file.tell() + remaining
        while self.file.tell() < chunkend:
            try:
                boxsize,boxtype,skip = self.scan_box()
            except EOFError:
                break
            iprint("Box Found: '%s' of length %u" % (boxtype, boxsize))
            self.file.seek(skip, os.SEEK_CUR)
        ipop()

#----------------------------------------------------------------
if __name__ == '__main__':
    print("Starting")
    try:
        mp4 = ISOBMFF()
        mp4.open("sample-video.mp4")
        mp4.scan()
        mp4.close()
    except IOError as e:
        print("ERROR: " + str(e))
    print("Done.")
