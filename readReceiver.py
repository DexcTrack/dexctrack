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

# Support python3 print syntax in python2
from __future__ import print_function

#import datetime
import sys
import sqlite3
import threading
import serial
import readdata
import database_records
#from traceback import print_exc


class readReceiverBase(readdata.Dexcom):
    _lock = threading.Lock()

    # We don't want to try to re-open a port which has already been opened,
    # so we include an optional 'port' argument, which can
    # be used to specify an existing, open port.
    def __init__(self, portname, port=None, dbg = False):
        self._port_name = portname
        readdata.Dexcom.__init__(self, portname, port, dbg)
        #print ('readReceiverBase() __init__ running. _port =', self._port, ', _port_name =', self._port_name, ', port =', port)

    def GetSerialNumber(self):
        #print ('readReceiverBase() GetSerialNumber running')
        self._lock.acquire()
        try:
            #print ('readReceiverBase.GetSerialNumber() : self._port_name =', self._port_name)
            if not self._port_name:
                dport = self.FindDevice()
                self._port_name = dport

            sernum = None
            if self._port_name:
                sernum = self.ReadManufacturingData().get('SerialNumber')
            self._lock.release()
            return sernum

        except Exception as e:
            #print ('GetSerialNumber() : Exception =', e)
            self.Disconnect()
            self._port_name = None
            self._lock.release()
            if sys.version_info < (3, 0):
                sys.exc_clear()
            return None

    def GetCurrentGlucoseAndTrend(self):
        db_read_status = 0
        self._lock.acquire()
        if not self._port_name:
            dport = self.FindDevice()
            self._port_name = dport
        try:
            respList = self.ReadRecords('EGV_DATA')
        except serial.SerialException as e:
            db_read_status = 2
            if self._debug_mode:
                print ('GetCurrentGlucoseAndTrend() : SerialException =', e)
                #print_exc()
            if sys.version_info < (3, 0):
                sys.exc_clear()
        except ValueError as e:
            db_read_status = 3
            if self._debug_mode:
                print ('GetCurrentGlucoseAndTrend() : ValueError Exception =', e)
                #print_exc()
            if sys.version_info < (3, 0):
                sys.exc_clear()
        except Exception as e:
            db_read_status = 4
            if self._debug_mode:
                print ('GetCurrentGlucoseAndTrend() : Exception =', e)
                #print_exc()
            if sys.version_info < (3, 0):
                sys.exc_clear()

        if respList:
            currentEgv = respList[-1]
            self._lock.release()
            return (currentEgv.glucose, currentEgv.full_trend, db_read_status)
        else:
            self._lock.release()
            return (None, None, db_read_status)

    def GetCurrentUserSettings(self):
        db_read_status = 0
        self._lock.acquire()
        if not self._port_name:
            dport = self.FindDevice()
            self._port_name = dport
        try:
            respList = self.ReadRecords('USER_SETTING_DATA')
        except serial.SerialException as e:
            db_read_status = 2
            if self._debug_mode:
                print ('GetCurrentUserSettings() : SerialException =', e)
                #print_exc()
            if sys.version_info < (3, 0):
                sys.exc_clear()
        except ValueError as e:
            db_read_status = 3
            if self._debug_mode:
                print ('GetCurrentUserSettings() : ValueError Exception =', e)
                #print_exc()
            if sys.version_info < (3, 0):
                sys.exc_clear()
        except Exception as e:
            db_read_status = 4
            if self._debug_mode:
                print ('GetCurrentUserSettings() : Exception =', e)
                #print_exc()
            if sys.version_info < (3, 0):
                sys.exc_clear()

        if respList:
            # The current User Settings are held in the last list element
            currentUserSettings = respList[-1]
            self._lock.release()
            return (currentUserSettings.transmitterPaired, currentUserSettings.highAlert, currentUserSettings.lowAlert, currentUserSettings.riseRate, currentUserSettings.fallRate, currentUserSettings.outOfRangeAlert, db_read_status)
        else:
            self._lock.release()
            return (None, None, None, None, None, None, db_read_status)

    def GetPowerInfo(self):
        #print ('readReceiverBase() GetPowerInfo running')
        self._lock.acquire()
        try:
            #print ('readReceiverBase.GetPowerInfo() : self._port_name =', self._port_name)
            if not self._port_name:
                dport = self.FindDevice()
                self._port_name = dport

            powerState = None
            powerLevel = 0
            if self._port_name:
                powerState = self.ReadBatteryState()
                if powerState is not None:
                    powerLevel = self.ReadBatteryLevel()

            self._lock.release()
            return (powerState, powerLevel)

        except Exception as e:
            if self._debug_mode:
                print ('GetPowerInfo() : Exception =', e)
            self.Disconnect()
            self._port_name = None
            self._lock.release()
            if sys.version_info < (3, 0):
                sys.exc_clear()
            return (None, 0)


    def DownloadToDb(self, dbPath):
        db_read_status = 0  # 0 = success, non-zero = failure
        self._lock.acquire()
        if self._port_name is not None:
            #now = datetime.datetime.now()
            #print ('readReceiver.py : DownloadToDb() : Reading device at', str(now))
            conn = sqlite3.connect(dbPath)
            try:
                curs = conn.cursor()

                # Earlier releases had a UserSettings table, but it sucked up a huge amount of storage space,
                # and didn't provide anything useful. So, if that table exists, we'll drop it and run
                # vacuum to free up 97% of the disk space.
                usCheckReq = "SELECT count(*) from sqlite_master where type='table' and name='UserSettings'"
                curs.execute(usCheckReq)
                sqlData = curs.fetchone()
                if sqlData[0] > 0:
                    print ('Deleting UserSettings table from database')
                    curs.execute('DROP TABLE IF EXISTS UserSettings;')
                    curs.execute('VACUUM;')

                curs.execute('CREATE TABLE IF NOT EXISTS EgvRecord( sysSeconds INT PRIMARY KEY, dispSeconds INT, full_glucose INT, glucose INT, testNum INT, trend INT);')
                insert_egv_sql = '''INSERT OR IGNORE INTO EgvRecord( sysSeconds, dispSeconds, full_glucose, glucose, testNum, trend) VALUES (?, ?, ?, ?, ?, ?);'''

                respList = self.ReadRecords('EGV_DATA')
                #printJustOne = True
                for cgm_rec in respList:
                    #if printJustOne:
                        #print ('EGV_DATA : raw_data =', ' '.join(' %02x' % ord(c) for c in cgm_rec.raw_data))
                        #printJustOne = False
                    curs.execute(insert_egv_sql, (cgm_rec.system_secs, cgm_rec.display_secs, cgm_rec.full_glucose, cgm_rec.glucose, cgm_rec.testNum, cgm_rec.full_trend))

                curs.execute('CREATE TABLE IF NOT EXISTS UserEvent( sysSeconds INT PRIMARY KEY, dispSeconds INT, meterSeconds INT, type INT, subtype INT, value INT, xoffset REAL, yoffset REAL);')
                insert_evt_sql = '''INSERT OR IGNORE INTO UserEvent( sysSeconds, dispSeconds, meterSeconds, type, subtype, value, xoffset, yoffset) VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''

                respList = self.ReadRecords('USER_EVENT_DATA')
                for evt_rec in respList:
                    #print ('raw_data =',' '.join(' %02x' % ord(c) for c in evt_rec.raw_data))
                    #print ('UserEvent(', evt_rec.system_secs, ',', evt_rec.display_secs, ', ', evt_rec.meter_secs, ', ', evt_rec.event_type, ', ', evt_rec.event_sub_type, ',', evt_rec.event_value)
                    curs.execute(insert_evt_sql, (evt_rec.system_secs, evt_rec.display_secs, evt_rec.meter_secs, evt_rec.int_type, evt_rec.int_sub_type, evt_rec.int_value, 0.0, 0.0))

                curs.execute('CREATE TABLE IF NOT EXISTS Config( id INT PRIMARY KEY CHECK (id = 0), displayLow REAL, displayHigh REAL, legendX REAL, legendY REAL, glUnits STR);')
                insert_cfg_sql = '''INSERT OR IGNORE INTO Config( id, displayLow, displayHigh, legendX, legendY, glUnits) VALUES (0, ?, ?, ?, ?, ?);'''
                # If no instance exists, set default values 75 & 200. Otherwise, do nothing.
                curs.execute(insert_cfg_sql, (75.0, 200.0, 0.01, 0.99, 'mg/dL'))

                respList = self.ReadGlucoseUnit()
                #print ('self.ReadGlucoseUnit() =', respList)
                if respList is not None:
                    update_cfg_sql = '''UPDATE Config SET glUnits = ? WHERE id = ?;'''
                    curs.execute(update_cfg_sql, ('%s'%respList, 0))

                curs.execute('CREATE TABLE IF NOT EXISTS SensorInsert( sysSeconds INT PRIMARY KEY, dispSeconds INT, insertSeconds INT, state INT, number INT, transmitter STR);')
                insert_ins_sql = '''INSERT OR IGNORE INTO SensorInsert( sysSeconds, dispSeconds, insertSeconds, state, number, transmitter) VALUES (?, ?, ?, ?, ?, ?);'''

                respList = self.ReadRecords('INSERTION_TIME')
                for ins_rec in respList:
                    if (self.rr_version == 'g5') or (self.rr_version == 'g6'):
                        curs.execute(insert_ins_sql, (ins_rec.system_secs, ins_rec.display_secs, ins_rec.insertion_secs, ins_rec.state_value, ins_rec.number, ins_rec.transmitterPaired))
                    else:
                        curs.execute(insert_ins_sql, (ins_rec.system_secs, ins_rec.display_secs, ins_rec.insertion_secs, ins_rec.state_value, 0, ''))

                curs.execute('CREATE TABLE IF NOT EXISTS Calib( sysSeconds INT PRIMARY KEY, dispSeconds INT, meterSeconds INT, type INT, glucose INT, testNum INT, xx INT);')
                insert_cal_sql = '''INSERT OR IGNORE INTO Calib( sysSeconds, dispSeconds, meterSeconds, type, glucose, testNum, xx) VALUES (?, ?, ?, ?, ?, ?, ?);'''

                respList = self.ReadRecords('METER_DATA')
                for cal_rec in respList:
                    #print ('raw_data =',' '.join(' %02x' % ord(c) for c in cal_rec.raw_data))
                    #print ('Calib(', cal_rec.system_secs, ',', cal_rec.display_secs, ', ', cal_rec.meter_secs, ', ', cal_rec.record_type, ', ', cal_rec.calib_gluc, ',', cal_rec.testNum)
                    curs.execute(insert_cal_sql, (cal_rec.system_secs, cal_rec.display_secs, cal_rec.meter_secs, cal_rec.record_type, cal_rec.calib_gluc, cal_rec.testNum, cal_rec.xx))

                del respList
                curs.close()
                conn.commit()
            except sqlite3.Error as e:
                print ('DownloadToDb() : Rolling back SQL changes due to exception =', e)
                db_read_status = 1
                curs.close()
                conn.rollback()
                if sys.version_info < (3, 0):
                    sys.exc_clear()
            except serial.SerialException as e:
                db_read_status = 2
                if self._debug_mode:
                    print ('DownloadToDb() : SerialException =', e)
                    #print_exc()
                if sys.version_info < (3, 0):
                    sys.exc_clear()
            except ValueError as e:
                db_read_status = 3
                if self._debug_mode:
                    print ('DownloadToDb() : ValueError Exception =', e)
                    #print_exc()
                if sys.version_info < (3, 0):
                    sys.exc_clear()
            except Exception as e:
                db_read_status = 4
                if self._debug_mode:
                    print ('DownloadToDb() : Exception =', e)
                    #print_exc()
                if sys.version_info < (3, 0):
                    sys.exc_clear()
            conn.close()
        self._lock.release()
        return db_read_status

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
        'USER_SETTING_DATA': database_records.G5UserSettings,
    }

#-------------------------------------------------------------------------
class readReceiverG6(readReceiverBase):
    # G6 uses the same format as G5 for Meter Data, Insertion, and EGV data
    rr_version = 'g6'
    PARSER_MAP = {
        'USER_EVENT_DATA': database_records.EventRecord,
        'METER_DATA': database_records.G5MeterRecord,
        'CAL_SET': database_records.Calibration,
        'INSERTION_TIME': database_records.G5InsertionRecord,
        'EGV_DATA': database_records.G5EGVRecord,
        'SENSOR_DATA': database_records.SensorRecord,
        'USER_SETTING_DATA': database_records.G6UserSettings,
    }

#-------------------------------------------------------------------------


if __name__ == '__main__':
    mdport = readReceiverBase.FindDevice()
    if mdport:
        readSerialInstance = readReceiver(mdport, dbg = True)
        serialNum = readSerialInstance.GetSerialNumber()
        print ('serialNum =', serialNum)
        mDevType = readSerialInstance.GetDeviceType()

        if mDevType == 'g4':
            mReadDataInstance = readSerialInstance
        elif mDevType == 'g5':
            mReadDataInstance = readReceiverG5(mdport, dbg = True)
        elif mDevType == 'g6':
            mReadDataInstance = readReceiverG6(mdport, dbg = True)
        else:
            exit

        if mReadDataInstance:
            print ('Device version =', mReadDataInstance.rr_version)
            mReadDataInstance.LocateAndDownload()
