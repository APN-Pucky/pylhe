import gzip
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest
import skhep_testdata

import pylhe
from pylhe import LHEEvent

TEST_FILE_LHE_v1 = skhep_testdata.data_path("pylhe-testfile-pr29.lhe")
TEST_FILE_LHE_v3 = skhep_testdata.data_path("pylhe-testlhef3.lhe")
TEST_FILE_LHE_INITRWGT_WEIGHTS = skhep_testdata.data_path(
    "pylhe-testfile-powheg-box-v2-hvq.lhe"
)
TEST_FILE_LHE_RWGT_WGT = skhep_testdata.data_path("pylhe-testfile-powheg-box-v2-W.lhe")
TEST_FILES_LHE_POWHEG = [
    skhep_testdata.data_path("pylhe-testfile-powheg-box-v2-%s.lhe" % (proc))
    for proc in ["Z", "W", "Zj", "trijet", "directphoton", "hvq"]
]

def test_write_lhe_eventline():
    """
    """
    events = pylhe.read_lhe_with_attributes(TEST_FILE_LHE_v3)

    assert events
    for e in events:
        assert e.particles[0].tolhe() == "    5  -1   0   0 501   0  0.00000000e+00  0.00000000e+00  1.43229060e+02  1.43309460e+02  4.80000000e+00  0.0000e+00  0.0000e+00"
        break


def test_write_lhe_eventinfo():
    """
    """
    events = pylhe.read_lhe_with_attributes(TEST_FILE_LHE_v3)

    assert events
    for e in events:
        assert e.eventinfo.tolhe() == "  5     66  5.0109093000e+01  1.4137688000e+02  7.5563862000e-03  1.2114027000e-01"
        break


def test_write_lhe_event():
    """
    """
    events = pylhe.read_lhe_with_attributes(TEST_FILE_LHE_v3)

    assert events
    for e in events:
        assert e.tolhe() == """<event>
  5     66  5.0109093000e+01  1.4137688000e+02  7.5563862000e-03  1.2114027000e-01
    5  -1   0   0 501   0  0.00000000e+00  0.00000000e+00  1.43229060e+02  1.43309460e+02  4.80000000e+00  0.0000e+00  0.0000e+00
    2  -1   0   0 502   0  0.00000000e+00  0.00000000e+00 -9.35443170e+02  9.35443230e+02  3.30000000e-01  0.0000e+00  0.0000e+00
   24   1   1   2   0   0 -8.42588040e+01 -1.57085660e+02 -1.06296000e+02  2.22571620e+02  8.03980000e+01  0.0000e+00  0.0000e+00
    5   1   1   2 501   0 -1.36680730e+02 -3.63074240e+01 -4.06144730e+01  1.47215580e+02  4.80000000e+00  0.0000e+00  0.0000e+00
    1   1   1   2 502   0  2.20939540e+02  1.93393080e+02 -6.45303640e+02  7.08965480e+02  3.30000000e-01  0.0000e+00  0.0000e+00
<rwgt>
 <wgt id='1001'>  5.0109e+01</wgt>
 <wgt id='1002'>  4.5746e+01</wgt>
 <wgt id='1003'>  5.2581e+01</wgt>
 <wgt id='1004'>  5.0109e+01</wgt>
 <wgt id='1005'>  4.5746e+01</wgt>
 <wgt id='1006'>  5.2581e+01</wgt>
 <wgt id='1007'>  5.0109e+01</wgt>
 <wgt id='1008'>  4.5746e+01</wgt>
 <wgt id='1009'>  5.2581e+01</wgt>
</rwgt>
</event>"""
        break

def test_write_lhe_init():
    init = pylhe.read_lhe_init(TEST_FILE_LHE_v3)

    assert init["initInfo"].tolhe()  == "   2212   2212  4.0000000e+03  4.0000000e+03    -1    -1  21100  21100    -4     1"
    assert init["procInfo"][0].tolhe()  == " 5.0109086e+01  8.9185414e-02  5.0109093e+01    66"
    print(init["weightgroup"] )

    assert init.tolhe() == """<init>
   2212   2212  4.0000000e+03  4.0000000e+03    -1    -1  21100  21100    -4     1
 5.0109086e+01  8.9185414e-02  5.0109093e+01    66
<initrwgt>
  <weightgroup type="scale_variation" combine="envelope">
    <weight id="1001">muR=0.10000E+01 muF=0.10000E+01</weight>
    <weight id="1002">muR=0.10000E+01 muF=0.20000E+01</weight>
    <weight id="1003">muR=0.10000E+01 muF=0.50000E+00</weight>
    <weight id="1004">muR=0.20000E+01 muF=0.10000E+01</weight>
    <weight id="1005">muR=0.20000E+01 muF=0.20000E+01</weight>
    <weight id="1006">muR=0.20000E+01 muF=0.50000E+00</weight>
    <weight id="1007">muR=0.50000E+00 muF=0.10000E+01</weight>
    <weight id="1008">muR=0.50000E+00 muF=0.20000E+01</weight>
    <weight id="1009">muR=0.50000E+00 muF=0.50000E+00</weight>
  </weightgroup>
</initrwgt>
</init>"""

def test_write_lhe_init():
    init = pylhe.read_lhe_init(TEST_FILE_LHE_v3)
    events = pylhe.read_lhe_with_attributes(TEST_FILE_LHE_v3)
    #single test event
    events = [next(events)]

    assert pylhe.write_lhe_string(init, events) == """<LesHouchesEvents version="3.0">
<init>
   2212   2212  4.0000000e+03  4.0000000e+03    -1    -1  21100  21100    -4     1
 5.0109086e+01  8.9185414e-02  5.0109093e+01    66
<initrwgt>
  <weightgroup type="scale_variation" combine="envelope">
    <weight id="1001">muR=0.10000E+01 muF=0.10000E+01</weight>
    <weight id="1002">muR=0.10000E+01 muF=0.20000E+01</weight>
    <weight id="1003">muR=0.10000E+01 muF=0.50000E+00</weight>
    <weight id="1004">muR=0.20000E+01 muF=0.10000E+01</weight>
    <weight id="1005">muR=0.20000E+01 muF=0.20000E+01</weight>
    <weight id="1006">muR=0.20000E+01 muF=0.50000E+00</weight>
    <weight id="1007">muR=0.50000E+00 muF=0.10000E+01</weight>
    <weight id="1008">muR=0.50000E+00 muF=0.20000E+01</weight>
    <weight id="1009">muR=0.50000E+00 muF=0.50000E+00</weight>
  </weightgroup>
</initrwgt>
</init>
<event>
  5     66  5.0109093000e+01  1.4137688000e+02  7.5563862000e-03  1.2114027000e-01
    5  -1   0   0 501   0  0.00000000e+00  0.00000000e+00  1.43229060e+02  1.43309460e+02  4.80000000e+00  0.0000e+00  0.0000e+00
    2  -1   0   0 502   0  0.00000000e+00  0.00000000e+00 -9.35443170e+02  9.35443230e+02  3.30000000e-01  0.0000e+00  0.0000e+00
   24   1   1   2   0   0 -8.42588040e+01 -1.57085660e+02 -1.06296000e+02  2.22571620e+02  8.03980000e+01  0.0000e+00  0.0000e+00
    5   1   1   2 501   0 -1.36680730e+02 -3.63074240e+01 -4.06144730e+01  1.47215580e+02  4.80000000e+00  0.0000e+00  0.0000e+00
    1   1   1   2 502   0  2.20939540e+02  1.93393080e+02 -6.45303640e+02  7.08965480e+02  3.30000000e-01  0.0000e+00  0.0000e+00
<rwgt>
 <wgt id='1001'>  5.0109e+01</wgt>
 <wgt id='1002'>  4.5746e+01</wgt>
 <wgt id='1003'>  5.2581e+01</wgt>
 <wgt id='1004'>  5.0109e+01</wgt>
 <wgt id='1005'>  4.5746e+01</wgt>
 <wgt id='1006'>  5.2581e+01</wgt>
 <wgt id='1007'>  5.0109e+01</wgt>
 <wgt id='1008'>  4.5746e+01</wgt>
 <wgt id='1009'>  5.2581e+01</wgt>
</rwgt>
</event>
</LesHouchesEvents>"""


def test_write_read_lhe_identical():
    pass