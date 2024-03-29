import atexit
from datetime import datetime
from enum import Enum
import os
from os import listdir
from os.path import isfile, join
from random import randint
import shutil
import signal


missed_logs_queue = []


class LoggerLevels(Enum):
    INFO = 'LOGGER_LEVEL_INFO'
    ERROR = 'LOGGER_LEVEL_ERROR'
    FATAL = 'LOGGER_LEVEL_FATAL'


def info():
    return LoggerLevels.INFO.value


def error():
    return LoggerLevels.ERROR.value


def fatal():
    return LoggerLevels.FATAL.value


class Logger:
    def __init__(self, logging_enabled: bool):
        self.__logging_enabled = logging_enabled
        if not logging_enabled:
            return
        signal.signal(signal.SIGINT, self._handler)
        signal.signal(signal.SIGTERM, self._handler)
        atexit.register(self._exit_at_close)
        self.__logs_directory = '../Logs'
        self.__log_file_directory = 'LogFiles'
        self.__log_ending = '_log_file.txt'
        self.__log_ending_old = '_old_log_file.txt'
        self.__log_ending_temp = '_temp_log_file.txt'
        self.__log_file_name = ''
        self.__log_file_short_name = ''
        self.__log_file_path = ''
        self._init_log_file()
        self.__file = self._open_log_file()
        self.write_log(info(), 'Successfully created log file!')

    def _init_log_file(self):
        cur_dir = os.getcwd()
        os.chdir(self.__logs_directory)
        self.__log_file_path = os.getcwd() + '/' + self.__log_file_directory
        files = []
        for file in listdir(self.__log_file_directory):
            cur_file = join(self.__log_file_directory, file)
            if isfile(cur_file) and cur_file.endswith(self.__log_ending):
                files.append(file)
        os.chdir(cur_dir)
        valid_digits = []
        for file_name in files:
            digit = file_name.split(self.__log_ending)[0]
            try:
                int(digit)
            except ValueError:
                continue
            valid_digits.append(digit)
        rand_int = randint(1000000, 9999999)
        while rand_int in valid_digits:
            rand_int = randint(1000000, 9999999)
        self.__log_file_name += str(rand_int) + self.__log_ending_temp
        self.__log_file_short_name = str(rand_int)
        self.__log_file_path += '/' + self.__log_file_name

    def file_name(self):
        if not self.__logging_enabled:
            return None
        return self.__log_file_name

    def short_file_name(self):
        if not self.__logging_enabled:
            return None
        return self.__log_file_short_name

    def file_path(self):
        if not self.__logging_enabled:
            return None
        return self.__log_file_path

    def _open_log_file(self):
        if not self.__logging_enabled:
            return None
        cur_dir = os.getcwd()
        os.chdir(self.__logs_directory)
        log_file_path = self.__log_file_directory + '/' + self.__log_file_name
        try:
            with open(log_file_path, 'a'):  # testing to see if file name is valid
                pass
        except FileNotFoundError:  # ignore this because duplicate errors in console
            pass
        except OSError:
            raise Exception(f'Error opening to {self.__log_file_name}')
        file = open(log_file_path, 'a')
        os.chdir(cur_dir)
        return file

    def _close_log_file(self):
        if not self.__logging_enabled:
            return
        self.__file.close()

    def is_open(self):
        if not self.__logging_enabled:
            return None
        return not self.__file.closed

    def _handler(self, *args):
        if not self.__logging_enabled:
            return
        _ = args
        self._close_log_file()
        self._change_file_state(self.__log_file_short_name)
        self.__logging_enabled = False
        # send_mail
        exit(1)

    def _exit_at_close(self):
        if not self.__logging_enabled:
            return
        try:
            if type(self.__file) != str and self.is_open():
                self._close_log_file()
                self._change_file_state(self.__log_file_short_name)
                self.__logging_enabled = False
                # send_mail
        except AttributeError:
            pass

    def _change_file_state(self, to_name: str):
        if not self.__logging_enabled:
            return
        cur_dir = os.getcwd()
        os.chdir(self.__logs_directory + '/' + self.__log_file_directory)
        current_log_file_exists = False
        if os.path.exists(to_name + self.__log_ending):  # if current log file exists
            current_log_file_exists = True  # change the flag
            shutil.copyfile(to_name + self.__log_ending, to_name + self.__log_ending_old)  # copy current log file to
            # old log file so that we save the previous log file
        shutil.copyfile(to_name + self.__log_ending_temp, to_name + self.__log_ending)  # copy the temp log file to
        # current log file, saving that as the new log file
        os.remove(to_name + self.__log_ending_temp)  # remove the temp log file, no more use for it
        if os.path.exists(to_name + self.__log_ending_old) and current_log_file_exists:  # if the old log file exists
            # and the current log file also exists, add an extra line to the end of the old log file to signify
            # that it won't be written to anymore
            with open(to_name + self.__log_ending_old, 'a') as old_file:
                old_file.write('!!The state of this log file has been changed. New logs will no longer be written!!\n')
        os.chdir(cur_dir)

    def write_log(self, logger_level: LoggerLevels, logger_message: str):
        if not self.__logging_enabled:
            return
        if os.path.exists(self.file_path()):
            if self.is_open():
                while len(missed_logs_queue) > 0:
                    missed_log = missed_logs_queue.pop(0)
                    missed_log_log_level = missed_log[0]
                    missed_log_log_message = missed_log[1]
                    missed_log_date_and_time = missed_log[2]
                    self.__file.write(
                        f'!!MISSED_LOG!! :: DateTime - [{missed_log_date_and_time}] :: LoggerLevel - '
                        f'{missed_log_log_level} :: LoggerMessage - {missed_log_log_message}\n')
                    self.__file.flush()
                date_and_time = datetime.now().strftime('%m-%d-%Y %H:%M:%S')
                self.__file.write(f'DateTime - [{date_and_time}] :: LoggerLevel - {logger_level} :: LoggerMessage - '
                                  f'{logger_message}\n')
                self.__file.flush()
        else:
            self.__file = self._open_log_file()
            missed_date_and_time = datetime.now().strftime('%m-%d-%Y %H:%M:%S')
            missed_logs_queue.append([logger_level, logger_message, missed_date_and_time])

    def rename_log_file(self, to_name: str):
        if not self.__logging_enabled:
            return
        cur_dir = os.getcwd()
        os.chdir(self.__logs_directory + '/' + self.__log_file_directory)
        new_file_name = to_name + self.__log_ending_temp
        os.rename(self.__log_file_name, new_file_name)
        os.chdir(cur_dir)
        self.__log_file_name = new_file_name
        self.__log_file_short_name = to_name
        self.__log_file_path = '/'.join(self.__log_file_path.split('/')[0:-1]) + '/' + new_file_name
        self.write_log(info(), 'Renamed the log file successfully.')
