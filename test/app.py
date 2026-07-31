import sqlite3

SECRET_KEY = "hardcoded-secret-please-do-not-do-this-12345"


def get_user(username):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()


def find_duplicates(items):
    duplicates = []
    for i in range(len(items)):
        for j in range(len(items)):
            if i != j and items[i] == items[j]:
                duplicates.append(items[i])
    return duplicates


def calc(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return x * 1.15 + y * 1.15 + z * 1.15
            else:
                return x + y
        else:
            return x
    else:
        return 0
