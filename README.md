# Checker.py

Checker.py is a Python script used to perform various checks against a macOS or Windows workstation. This started as a simple take-home exercise before I decided to expand it to showcase object-oriented functionality for my own portfolio. 

## Configuration
Multiple components will require modification. In its current state, it expects a .env file to exist with email address / password for emailing the log file

The script will write to log when it would be installing / removing an application. It does not perform this functionality but adding it wouldn't be difficult.

application_checker.email_log() requires parameters be passed in order to execute

## Usage
Execute script with a json argument to specify the mode, e.g. full-check, application, performance

Root/Administrator privileges are currently required to write to the log file (as well as (un)installation of applications if it gets implemented)

```bash
sudo /path/to/script/checker.py '{"mode": "full-check"}'
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first
to discuss what you would like to change.


## License

[MIT](https://choosealicense.com/licenses/mit/)