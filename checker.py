#!/usr/bin/env python3

"""
Filename: checker.py
Author: D
Date: 2024-06-18
Description: This script attempts to perform various app installation
    and performance checks against a macOS device.
    Will automatically email log file depending on results of checker functions
Usage:
- checker.py [options]
"""

import shutil
import sys
import json
import logging
import os
import subprocess
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

state = {'ship_log': False}


def main():
    """
    Main function
    Processes argument passed to python script. Establishes logging.
    Executes checker functions depending on what argument is passed.
    """
    # Accepts input arg(s) in JSON format
    if len(sys.argv) < 2:
        print("A JSON-formatted argument is required, e.g. '{\"mode\": \"full-check\"}' \n"
              "Please try again")
        sys.exit(1)
    arg = json.loads(sys.argv[1])
    mode = arg["mode"]

    # Establish logging
    logging.basicConfig(filename='/var/log/checker.log', filemode='w',
                        format='%(asctime)s - %(levelname)s -  %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S', level=logging.INFO)
    logging.info("Executing checker")

    # Check which mode is selected and execute accordingly
    match mode:
        case 'full-check':
            app_mode()
            performance_check()
        case 'applications':
            app_mode()
        case 'performance':
            performance_check()
        case _:
            app_mode()
            performance_check()
    if state['ship_log']:
        email_log('Test Email 2', 'Log file', 'email@example.com', '/var/log/checker.log', 'smtp.mail.me.com', 587)


def errors(e, message="An error occurred"):
    """
    Default error function. Will probably delete.
    :param e:
    :param message:
    :return:
    """
    logging.error(message)
    logging.error(e.args)
    print(e.args)
    state['ship_log'] = True


def app_mode():
    """
    Function invoked when full-check or applications mode is selected.
    Attempts to check for and, if needed, download and install required applications.
    Attempts to check for and, if needed, remove blocklisted application.
    """
    app_adder('Zoom', 'https://zoom.us/')
    app_adder('Google Chrome', 'https://www.google.com/')
    app_adder('Slack', 'https://www.slack.com/')
    app_remover('SpywareApp')


def app_adder(app_bundle, url, max_tries=3):
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
    state['ship_log'] = True


def app_remover(app_bundle):
    """
    Attempts to check for and, if needed, remove blocklisted application.

    app_bundle: Application name without app bundle extension, e.g. SpywareApp
    """
    app_found = os.path.isdir(f'/Applications/{app_bundle}.app')
    if app_found:
        logging.warning('%s exists. Uninstalling it.', app_bundle)
        # shutil.rmtree(f'/Applications/{app_bundle}.app')
        state['ship_log'] = True
    else:
        logging.info('%s not found.', app_bundle)


def performance_check():
    """
    Function invoked when full-check or performance  mode is selected.
    Attempts to execute performance checker functions: disk space, uptime, encryption status.
    The results of these checks are passed back as an integer, 0 if passed, 1 if failed or error

    If performance_total remains 0 after all three checkers,
        the app_adder function attempts to install Spotify.
    If performance_total is any int other than 0,
        it will look for Spotify and, if found, attempt to remove it.
    """
    performance_total = 0

    # Determine if adequate disk space is still available. Return 0 if space is >20%
    performance_total += disk_space_check()
    # Determine if uptime limit has been reached. Return 0 if uptime < 30 days
    performance_total += uptime_check()
    # Determine encryption status. Return 0 if it is enabled.
    performance_total += encryption_check()

    if performance_total == 0:
        try:
            logging.info("Performance checks passed. Attempting to install optional app.")
            app_adder("Spotify", "https://spotify.com")
        except Exception as e:
            errors(e, "Failed to install optional app")

    else:
        try:
            logging.info("Performance checks not satisfactory. Attempting to remove optional app.")
            app_remover("Spotify")
        except Exception as e:
            errors(e, "Failed to remove optional app")


def disk_space_check() -> int:
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
        state['ship_log'] = True
        return 1
    except Exception as e:
        errors(e, "Error while checking disk space")
        return 1


def uptime_check() -> int:
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
            state['ship_log'] = True
            return 1
        logging.info('Uptime is %s', output)
        return 0
    except Exception as e:
        errors(e, "Error while checking uptime")
        return 1


def encryption_check() -> int:
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
        state['ship_log'] = True
        return 1
    except Exception as e:
        errors(e, "Error while checking encryption status")
        return 1


def email_log(subject, content, recipient_email, attachment_path=None, smtpserver=None, portnumber=None):
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
    email_address = os.getenv('EMAIL_ADDRESS')
    email_password = os.getenv('EMAIL_PASSWORD')

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


if __name__ == '__main__':
    main()
