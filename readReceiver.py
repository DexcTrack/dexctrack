###############################################################################
#    Copyright 2018 Steve Erlenborn
###############################################################################
#    This file is part of DexcTrack.
#
#    DexcTrack is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    DexcTrack is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

import datetime
import sys
import time
import sqlite3
import grp
import pwd
import os
import threading
import serial
#------------------------------
import readdata
import database_records


class readReceiverBase(readdata.Dexcom):
    _lock = threading.Lock()

    def __init__(self, portname):
        self._port = None
        self._port_name = portname
        readdata.Dexcom.__init__(self, self._port_name)

    @classmethod
    def GetSerialNumber(cls):
        cls._lock.acquire()
        try:
            receiverPort = cls.FindDevice()
            if not receiverPort:
                cls._lock.release()
                return None
            else:
                dex = cls(receiverPort)
                sernum = dex.ReadManufacturingData().get('SerialNumber')
                cls._lock.release()
                return sernum
        except Exception as e:
            print 'GetSerialNumber() : Exception =', e
            cls._lock.release()
            return None


    @classmethod
    def DownloadToDb(cls, dbPath):
        cls._lock.acquire()
        receiverPort = cls.FindDevice()
        if not receiverPort:
            #sys.stderr.write('Could not find Dexcom G4|G5 Receiver!\n')
            cls._lock.release()
            return
        else:
            dex = cls(receiverPort)
            #now = datetime.datetime.now()
            #print 'readReceiver.py : DownloadToDb() : Reading device at', str(now)

            downloadDevType = cls.GetDeviceType()  # g4 | g5 | g6
            #print 'downloadDevType =',downloadDevType

            #for uev_rec in dex.ReadRecords('USER_EVENT_DATA'):
                #print 'raw_data =',' '.join(' %02x' % ord(c) for c in uev_rec.raw_data)

            #for cal_rec in dex.ReadRecords('CAL_SET'):
                #print 'raw_data =',' '.join(' %02x' % ord(c) for c in cal_rec.raw_data)

            #for ins_rec in dex.ReadRecords('INSERTION_TIME'):
                #print 'raw_data =',' '.join(' %02x' % ord(c) for c in ins_rec.raw_data)

            #--------------------------------------------------------------------------------
            conn = sqlite3.connect(dbPath)
            try:
                curs = conn.cursor()

                # The PARSER_MAP for G4 doesn't include USER_SETTING_DATA, so restrict use of it to newer releases
                if (downloadDevType == 'g5') or (downloadDevType == 'g6'):
                    curs.execute('CREATE TABLE IF NOT EXISTS UserSettings( sysSeconds INT, dispSeconds INT, transmitter STR, high INT, low INT, rise INT, fall INT, outOfRange INT);')
                    insert_usr_sql = '''INSERT OR IGNORE INTO UserSettings( sysSeconds, dispSeconds, transmitter, high, low, rise, fall, outOfRange) VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''

                    respList = dex.ReadRecords('USER_SETTING_DATA')
                    for usr_rec in respList:
                        curs.execute(insert_usr_sql, (usr_rec.system_secs, usr_rec.display_secs, usr_rec.transmitterPaired, usr_rec.highAlert, usr_rec.lowAlert, usr_rec.riseAlert, usr_rec.fallAlert, usr_rec.outOfRangeAlert))


                curs.execute('CREATE TABLE IF NOT EXISTS EgvRecord( sysSeconds INT PRIMARY KEY, dispSeconds INT, full_glucose INT, glucose INT, testNum INT, trend INT);')
                insert_egv_sql = '''INSERT OR IGNORE INTO EgvRecord( sysSeconds, dispSeconds, full_glucose, glucose, testNum, trend) VALUES (?, ?, ?, ?, ?, ?);'''

                respList = dex.ReadRecords('EGV_DATA')
                for cgm_rec in respList:
                    #print 'raw_data =',' '.join(' %02x' % ord(c) for c in cgm_rec.raw_data)
                    curs.execute(insert_egv_sql, (cgm_rec.system_secs, cgm_rec.display_secs, cgm_rec.full_glucose, cgm_rec.glucose, cgm_rec.testNum, cgm_rec.full_trend))

                curs.execute('CREATE TABLE IF NOT EXISTS UserEvent( sysSeconds INT PRIMARY KEY, dispSeconds INT, meterSeconds INT, type INT, subtype INT, value INT, xoffset REAL, yoffset REAL);')
                insert_evt_sql = '''INSERT OR IGNORE INTO UserEvent( sysSeconds, dispSeconds, meterSeconds, type, subtype, value, xoffset, yoffset) VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''

                respList = dex.ReadRecords('USER_EVENT_DATA')
                for evt_rec in respList:
                    #print 'raw_data =',' '.join(' %02x' % ord(c) for c in evt_rec.raw_data)
                    #print 'UserEvent(',evt_rec.system_secs,',',evt_rec.display_secs,',',evt_rec.meter_secs(),',',evt_rec.event_type,',',evt_rec.event_sub_type,',',evt_rec.event_value
                    curs.execute(insert_evt_sql, (evt_rec.system_secs, evt_rec.display_secs, evt_rec.meter_secs, evt_rec.int_type, evt_rec.int_sub_type, evt_rec.int_value, 0.0, 0.0))

                curs.execute('CREATE TABLE IF NOT EXISTS Config( id INT PRIMARY KEY CHECK (id = 0), displayLow REAL, displayHigh REAL, legendX REAL, legendY REAL, glUnits STR);')
                insert_cfg_sql = '''INSERT OR IGNORE INTO Config( id, displayLow, displayHigh, legendX, legendY, glUnits) VALUES (0, ?, ?, ?, ?, ?);'''
                # If no instance exists, set default values 75 & 200. Otherwise, do nothing.
                curs.execute(insert_cfg_sql, (75.0, 200.0, 0.01, 0.99, 'mg/dL'))

                respList = dex.ReadGlucoseUnit()
                #print 'dex.ReadGlucoseUnit() =',respList
                if respList is not None:
                    update_cfg_sql = '''UPDATE Config SET glUnits = ? WHERE id = ?;'''
                    curs.execute(update_cfg_sql, ('%s'%respList,0))

                curs.execute('CREATE TABLE IF NOT EXISTS SensorInsert( sysSeconds INT PRIMARY KEY, dispSeconds INT, insertSeconds INT, state INT, number INT, transmitter STR);')
                insert_ins_sql = '''INSERT OR IGNORE INTO SensorInsert( sysSeconds, dispSeconds, insertSeconds, state, number, transmitter) VALUES (?, ?, ?, ?, ?, ?);'''

                respList = dex.ReadRecords('INSERTION_TIME')
                for ins_rec in respList:
                    if (downloadDevType == 'g5') or (downloadDevType == 'g6'):
                        curs.execute(insert_ins_sql, (ins_rec.system_secs, ins_rec.display_secs, ins_rec.insertion_secs, ins_rec.state_value, ins_rec.number, ins_rec.transmitterPaired))
                    else:
                        curs.execute(insert_ins_sql, (ins_rec.system_secs, ins_rec.display_secs, ins_rec.insertion_secs, ins_rec.state_value, 0, ''))

                del respList
                curs.close()
                conn.commit()
            except Exception as e:
                print 'DownloadToDb() : Rolling back SQL changes due to exception =', e
                curs.close()
                conn.rollback()
            conn.close()
            cls._lock.release()

#-------------------------------------------------------------------------
class readReceiver(readReceiverBase):
    # The G4 version of this class uses the default PARSER_MAP
    # but python requires us to put something in our class declaration,
    # so we declare a class variable 'rr_version'.
    rr_version = 'g4'

#-------------------------------------------------------------------------
class readReceiverG5(readReceiverBase):
    rr_version = 'g5'
    PARSER_MAP = {
        'USER_EVENT_DATA': database_records.EventRecord,
        'METER_DATA': database_records.G5MeterRecord,
        'CAL_SET': database_records.Calibration,
        'INSERTION_TIME': database_records.G5InsertionRecord,
        'EGV_DATA': database_records.G5EGVRecord,
        'SENSOR_DATA': database_records.SensorRecord,
        'USER_SETTING_DATA': database_records.UserSettings,
    }

#-------------------------------------------------------------------------
class readReceiverG6(readReceiverBase):
    # Don't yet know if we need any differences for G6 verses G5
    rr_version = 'g6'
    PARSER_MAP = {
        'USER_EVENT_DATA': database_records.EventRecord,
        'METER_DATA': database_records.G5MeterRecord,
        'CAL_SET': database_records.Calibration,
        'INSERTION_TIME': database_records.G5InsertionRecord,
        'EGV_DATA': database_records.G5EGVRecord,
        'SENSOR_DATA': database_records.SensorRecord,
        'USER_SETTING_DATA': database_records.UserSettings,
    }

#-------------------------------------------------------------------------


if __name__ == '__main__':
    serialNum = readReceiver.GetSerialNumber()
    if serialNum:
        print 'serialNum =', serialNum
        dport = readReceiver.FindDevice()
        print 'dport =', dport
        dinstance = readReceiver(dport)
        print 'dinstance.GetDeviceType =',dinstance.GetDeviceType()
        myDevice = readdata.GetDevice(dport)
        print 'readdata.GetDevice =', myDevice
        if myDevice:
            myDevice.LocateAndDownload()
