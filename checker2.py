#!/usr/bin/env python3

"""
Filename: checker2.py
Author: David Luis Clary
Date: 2024-06-20
Description: This script attempts to perform various app installation
    and performance checks against a macOS device.
    Will automatically email log file depending on results of checker functions
Usage:
- checker2.py [options]
"""

from abc import ABC, abstractmethod
import shutil
import sys
import json
import logging
import os
import subprocess
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv


class BaseChecker:
    """
    Base class for all checkers. Establishes error handling function and email_log function
    """
    def __init__(self):
        self.ship_log = False

    def errors(self, e, message="An error occurred"):
        logging.error(message)
        logging.error(e.args)
        print(e.args)
        self.ship_log = True

    def email_log(self,
                  subject=None,
                  content=None,
                  recipient_email=None,
                  attachment_path=None,
                  smtpserver=None,
                  portnumber=None):
        """
        Emails the log file with a subject line of
            a datestamp and device serial number / hostname.
        Function expects a .env file to exist with sender email / password
        Process likely simpler with a post request to a webhook, e.g. Slack workflows

        subject: subject line of the email
        content: email body message
        recipient_email: whomever should receive the emailed log file
        attachment_path: path to the log file; defaults to None
        """
        load_dotenv()
        # email_address = os.getenv('EMAIL_ADDRESS')
        # email_password = os.getenv('EMAIL_PASSWORD')

        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = os.getenv('EMAIL_ADDRESS')
        msg['To'] = recipient_email
        msg.set_content(content)

        # Attach a file if provided
        if attachment_path:
            with open(attachment_path, 'rb') as file:
                file_data = file.read()
                file_name = os.path.basename(attachment_path)
                msg.add_attachment(file_data, maintype='application', subtype='octet-stream', filename=file_name)

        try:
            with smtplib.SMTP(smtpserver, portnumber) as server:
                server.starttls()
                print("Starting TLS...")
                server.login(os.getenv('EMAIL_ADDRESS'), os.getenv('EMAIL_PASSWORD'))
                print("Login successful...")
                server.send_message(msg)
                print("Email sent successfully")
        except smtplib.SMTPAuthenticationError as e:
            self.errors(e, "SMTP Authentication error")
        except (ValueError, TypeError) as e:
            self.errors(e, "Value or type error occurred while sending email")
        except Exception as e:
            print(f"Error sending email: {e}")


class PerformanceChecker(BaseChecker, ABC):
    """
    Abstract class inheriting from BaseChecker to perform performance checks against a device.
    Will also gather the device's serial number.
    """
    def __init__(self, app_checker):
        super().__init__()
        self.app_checker = app_checker

    @abstractmethod
    def disk_space_check(self) -> int:
        pass

    @abstractmethod
    def uptime_check(self) -> int:
        pass

    @abstractmethod
    def encryption_check(self) -> int:
        pass

    @abstractmethod
    def get_serial_number(self):
        pass

    def add_app(self, app_bundle, url):
        self.app_checker.app_adder(app_bundle, url)


class ApplicationChecker(BaseChecker, ABC):
    """
    Abstract class inheriting from BaseChecker to perform application checks against a device.
    """
    @abstractmethod
    def app_adder(self, app_bundle: str, url: str):
        pass

    @abstractmethod
    def app_remover(self, app_bundle: str):
        pass


class MacOSPerformanceChecker(PerformanceChecker):
    """
    Class inheriting from PerformanceChecker to perform performance checks against a macOS device.
    Also gathers the macOS device's serial number.
    """
    def disk_space_check(self) -> bool:
        """
        Attempts to calculate percentage of available disk space.
        If disk space > 20%, the function returns 0.
        If disk space is less than 20%, it will confirm that logs should be shipped and return a 1.
        """
        try:
            total, _, free = shutil.disk_usage("/")
            percent_free = round(free / total * 100, 2)
            if percent_free > 20.00:
                logging.info('%s%% available disk space', percent_free)
                return True
            logging.warning('%s%% available disk space', percent_free)
            self.ship_log = True
            return False
        except OSError as e:
            self.errors(e, "Error while checking disk space")
            return False
        except (ValueError, TypeError) as e:
            self.errors(e, "Value or type error occurred while sending email")
            return False
        except Exception as e:
            self.errors(e, "Error while checking disk space")
            return False

    def uptime_check(self) -> bool:
        """
        Attempts to calculate the system's uptime.
        If the uptime less than 30 days, the function will return a 0.
        If the uptime is greater than 30 days or an error occurs,
            it will confirm that logs should be shipped and return a 1.
        """
        uptime_limit = 30 * 24 * 60 * 60
        try:
            output = subprocess.check_output(['uptime']).decode('utf-8').strip()
            if "days" in output:
                num_days = int(output.split()[2])
                total_seconds = num_days * 24 * 3600
                if total_seconds < uptime_limit:
                    logging.info('Uptime is %s', output)
                    return True
                logging.warning('Uptime limit exceeded: %s', output)
                self.ship_log = True
                return False
            logging.info('Uptime is %s', output)
            return True
        except subprocess.CalledProcessError as e:
            self.errors(e, "Error while checking uptime")
            return False
        except (ValueError, TypeError) as e:
            self.errors(e, "Value or type error occurred while processing uptime")
            return False
        except Exception as e:
            self.errors(e, "An error occurred")
            return False

    def encryption_check(self) -> bool:
        """
        Attempts to determine encryption status.
        If encryption is On, the function will return a 0.
        If encryption is not On or an error occurs,
            it will confirm that logs should be shipped and return a 1.
        """
        try:
            output = subprocess.check_output(['fdesetup', 'status']).decode('utf-8').strip()
            if "On" in output:
                logging.info('File vault status: %s', output)
                return True
            logging.warning('File vault status: %s', output)
            self.ship_log = True
            return False
        except subprocess.CalledProcessError as e:
            self.errors(e, "Error while checking encryption")
            return False
        except (ValueError, TypeError) as e:
            self.errors(e, "Value or type error occurred while checking encryption")
            return False
        except Exception as e:
            self.errors(e, "Error while checking encryption status")
            return False

    def get_serial_number(self):
        """
        Attempts to gather and return the serial number of the macOS device.
        """
        try:
            output = subprocess.check_output(['system_profiler', 'SPHardwareDataType'])
            output = output.decode('utf-8')

            # Extract the serial number from the output
            for line in output.split('\n'):
                if "Serial Number (system):" in line:
                    serial_number = line.split(":")[1].strip()
                    return serial_number
                return None
        except subprocess.CalledProcessError as e:
            self.errors(e, "Error while checking serial number")
            return None


class MacOSApplicationChecker(ApplicationChecker):
    """
    Class inheriting from ApplicationChecker to perform application checks against a macOS device.
    """
    def app_adder(self, app_bundle, url, max_tries=3):
        """
        Attempts to determine if application is installed. If not found, it will attempt to install it.

        app_bundle: The name of the application, leaving off the bundle extension, e.g. Google Chrome
        url: The download URL of the application
        max_tries: maximum number of attempts to download/install the application

        """
        for attempt in range(1, max_tries + 1):
            app_found = os.path.isdir(f'/Applications/{app_bundle}.app')
            if app_found:
                logging.info('%s exists', app_bundle)
                return
            logging.info('Attempt %s: %s not found. Downloading.',
                         attempt, app_bundle)
            # Request app bundle's pkg or dmg using the url param.
            # Download to /var/tmp.
            logging.info('Download complete. Installing %s', app_bundle)
            # Install pkg or mount/copy app bundle from dmg.
            # Also, worthwhile to verify checksum if vendor offers source of truth.
        logging.error('Failed to install %s', app_bundle)
        self.ship_log = True

    def app_remover(self, app_bundle):
        """
        Attempts to check for and, if needed, remove blocklisted application.

        app_bundle: Application name without app bundle extension, e.g. SpywareApp
        """
        app_found = os.path.isdir(f'/Applications/{app_bundle}.app')
        if app_found:
            logging.warning('%s exists. Uninstalling it.', app_bundle)
            # shutil.rmtree(f'/Applications/{app_bundle}.app')
            self.ship_log = True
        else:
            logging.info('%s not found.', app_bundle)


class WindowsPerformanceChecker(PerformanceChecker):
    """
    Class inheriting from PerformanceChecker to perform performance checks against a Windows device.
    Will also gather the Windows device's serial number.
    """
    def disk_space_check(self) -> int:
        pass

    def uptime_check(self) -> int:
        pass

    def encryption_check(self) -> int:
        pass

    def get_serial_number(self):
        pass

class WindowsApplicationChecker(ApplicationChecker):
    """
    Class inheriting from ApplicationChecker to perform application checks against a Windows device.
    """
    def app_adder(self, app_bundle, url, max_tries=3):
        pass

    def app_remover(self, app_bundle):
        pass


# noinspection DuplicatedCode
def main():
    if len(sys.argv) < 2:
        print("A JSON-formatted argument is required, e.g. '{\"mode\": \"full-check\"}' \n"
              "Please try again")
        sys.exit(1)
    arg = json.loads(sys.argv[1])
    mode = arg["mode"]
    if os.name == 'posix':
        application_checker = MacOSApplicationChecker()
        performance_checker = MacOSPerformanceChecker(application_checker)
        log_path = '/var/log/checker.log'
    elif os.name == 'nt':
        application_checker = WindowsApplicationChecker()
        performance_checker = WindowsPerformanceChecker(application_checker)
        log_path = 'C:\\Logs\\checker.log'
    else:
        print("This script only works on macOS or Windows. Exiting.")
        sys.exit(1)
    logging.basicConfig(filename=log_path, filemode='w',
                        format='%(asctime)s - %(levelname)s -  %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
    logging.info("Executing checker")
    match mode:
        case 'full-check':
            application_checker.app_adder('Zoom', 'https://zoom.us')
            application_checker.app_adder('Google Chrome', 'https://www.google.com')
            application_checker.app_adder('Slack', 'https://www.slack.com')
            application_checker.app_remover('SpywareApp')
            if (performance_checker.disk_space_check()
                    and performance_checker.uptime_check()
                    and performance_checker.encryption_check()):
                performance_checker.add_app('Spotify', 'https://spotify.com')
        case 'applications':
            application_checker.app_adder('Zoom', 'https://zoom.us')
            application_checker.app_adder('Google Chrome', 'https://www.google.com')
            application_checker.app_adder('Slack', 'https://www.slack.com')
            application_checker.app_adder('Spotify', 'https://spotify.com')
            application_checker.app_remover('SpywareApp')
        case 'performance':
            if (performance_checker.disk_space_check()
                    and performance_checker.uptime_check()
                    and performance_checker.encryption_check()):
                performance_checker.add_app('Spotify', 'https://spotify.com')
        case _:
            application_checker.app_adder('Zoom', 'https://zoom.us')
            application_checker.app_adder('Google Chrome', 'https://www.google.com')
            application_checker.app_adder('Slack', 'https://www.slack.com')
            application_checker.app_remover('SpywareApp')
            if (performance_checker.disk_space_check()
                    and performance_checker.uptime_check()
                    and performance_checker.encryption_check()):
                performance_checker.add_app('Spotify', 'https://spotify.com')

    if application_checker.ship_log or performance_checker.ship_log:
        application_checker.email_log() #Parameters required


if __name__ == '__main__':
    main()
