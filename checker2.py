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


class BaseChecker(ABC):
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
            print(f"SMTP Authentication error: {e.smtp_code} - {e.smtp_error.decode('utf-8')}")
        except Exception as e:
            print(f"Error sending email: {e}")


class PerformanceChecker(BaseChecker):
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
    def get_serial_number(self) -> str:
        pass

    def get_hostname(self) -> str:
        pass

    def get_username(self) -> str:
        pass


class ApplicationChecker(BaseChecker):
    @abstractmethod
    def app_adder(self, app_bundle: str, url: str):
        pass

    @abstractmethod
    def app_remover(self, app_bundle: str):
        pass


class MacOSPerformanceChecker(PerformanceChecker):
    def disk_space_check(self) -> int:
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
                return 0
            logging.warning('%s%% available disk space', percent_free)
            self.ship_log = True
            return 1
        except Exception as e:
            self.errors(e, "Error while checking disk space")
            return 1

    def uptime_check(self) -> int:
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
                    return 0
                logging.warning('Uptime limit exceeded: %s', output)
                self.ship_log = True
                return 1
            logging.info('Uptime is %s', output)
            return 0
        except Exception as e:
            self.errors(e, "Error while checking uptime")
            return 1

    def encryption_check(self) -> int:
        """
        Attempts to determine encryption status.
        If encryption is On, the function will return a 0.
        If encryption is not On or an error occurs,
            it will confirm that logs should be shipped and return a 1.
        """
        try:
            output = subprocess.run(['fdesetup', 'status'], text=True, capture_output=True, check=True)
            fv_output = output.stdout.strip()
            if "On" in fv_output:
                logging.info('File vault status: %s', fv_output)
                return 0
            logging.warning('File vault status: %s', fv_output)
            self.ship_log = True
            return 1
        except Exception as e:
            self.errors(e, "Error while checking encryption status")
            return 1


class MacOSApplicationChecker(ApplicationChecker):
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
    def disk_space_check(self) -> int:
        pass

    def uptime_check(self) -> int:
        pass

    def encryption_check(self) -> int:
        pass


class WindowsApplicationChecker(ApplicationChecker):
    def app_adder(self, app_bundle, url, max_tries=3):
        pass

    def app_remover(self, app_bundle):
        pass


def main():
    if len(sys.argv) < 2:
        print("A JSON-formatted argument is required, e.g. '{\"mode\": \"full-check\"}' \n"
              "Please try again")
        sys.exit(1)
    arg = json.loads(sys.argv[1])
    mode = arg["mode"]
    logging.basicConfig(filename='/var/log/checker.log', filemode='w',
                        format='%(asctime)s - %(levelname)s -  %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
    logging.info("Executing checker")
    if os.name == 'posix':
        performance_checker = MacOSPerformanceChecker()
        application_checker = MacOSApplicationChecker()
    elif os.name == 'nt':
        performance_checker = WindowsPerformanceChecker()
        application_checker = WindowsApplicationChecker()
    else:
        raise NotImplementedError("This script only works on macOS or Windows.")

    match mode:
        case 'full-check':
            application_checker.app_adder('Zoom', 'https://zoom.us')
            application_checker.app_adder('Google Chrome', 'https://www.google.com')
            application_checker.app_adder('Slack', 'https://www.slack.com')
            application_checker.app_remover('SpywareApp')
            performance_checker.disk_space_check()
            performance_checker.uptime_check()
            performance_checker.encryption_check()
        case 'applications':
            application_checker.app_adder('Zoom', 'https://zoom.us')
            application_checker.app_adder('Google Chrome', 'https://www.google.com')
            application_checker.app_adder('Slack', 'https://www.slack.com')
            application_checker.app_remover('SpywareApp')
        case 'performance':
            performance_checker.disk_space_check()
            performance_checker.uptime_check()
            performance_checker.encryption_check()
        case _:
            application_checker.app_adder('Zoom', 'https://zoom.us')
            application_checker.app_adder('Google Chrome', 'https://www.google.com')
            application_checker.app_adder('Slack', 'https://www.slack.com')
            application_checker.app_remover('SpywareApp')
            performance_checker.disk_space_check()
            performance_checker.uptime_check()
            performance_checker.encryption_check()

    if application_checker.ship_log or performance_checker.ship_log:
        application_checker.email_log()


if __name__ == '__main__':
    main()