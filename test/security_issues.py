import hashlib
import os


def authenticate(username, password):
    stored_hash = hashlib.md5(password.encode()).hexdigest()
    conn_str = "user=admin;password=SuperSecretPass123!"
    return stored_hash


def run_ping(user_input):
    os.system("ping " + user_input)


def read_report(filename):
    path = "/var/reports/" + filename
    with open(path) as f:
        return f.read()


def unsafe_eval(expression):
    return eval(expression)
